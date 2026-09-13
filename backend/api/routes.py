from __future__ import annotations

import shutil
import tempfile
import uuid
import zipfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from backend.agent.agent import run_coding_task
from backend.core.config import settings
from backend.mcp.client import call_mcp
from backend.rag.pipeline import RAGPipeline
from backend.security.diff import apply_unified_diff
from backend.security.paths import SecurityError, safe_join
from backend.security.uploads import validate_filename

router = APIRouter(prefix="/api")
rag = RAGPipeline()

# Evaluation prototype: task state is intentionally small and in-memory.
# The deployed demo is single-process; persistent application state is not required.
TASKS: dict[str, dict] = {}


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=10)


class TaskRequest(BaseModel):
    task: str = Field(min_length=1, max_length=4000)
    workspace_id: str = Field(default="demo", pattern=r"^[a-zA-Z0-9_-]{1,64}$")


class ApprovalRequest(BaseModel):
    approved: bool


@router.get("/health")
def health():
    return {"status": "ok", "service": "sentinelforge"}


@router.get("/status")
async def status():
    return await call_mcp("system_status", {})


@router.post("/documents/ingest")
async def ingest(file: UploadFile = File(...)):
    try:
        filename = validate_filename(file.filename or "")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    data = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, "Upload exceeds configured size limit")
    settings.ensure_dirs()
    target = settings.upload_dir / filename
    target.write_bytes(data)
    try:
        return await call_mcp("ingest_content", {"file_path": filename})
    finally:
        target.unlink(missing_ok=True)


@router.get("/documents")
def list_documents():
    return {"documents": rag.documents(), "stats": rag.stats()}


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str):
    result = await call_mcp("delete_indexed_content", {"document_id": document_id})
    if not result.get("ok"):
        raise HTTPException(404, "Document not found")
    return {"ok": True, "deleted": document_id}


@router.post("/query")
async def query(request: QueryRequest):
    result = await call_mcp("retrieve_context", request.model_dump())
    if not result.get("ok", False):
        raise HTTPException(400, result.get("error", "Retrieval failed"))
    return result


@router.post("/repositories/upload")
async def upload_repository(file: UploadFile = File(...)):
    filename = Path(file.filename or "").name
    if filename != (file.filename or "") or not filename.lower().endswith(".zip"):
        raise HTTPException(400, "Repository upload must be a .zip file with a safe filename")
    data = await file.read(25 * 1024 * 1024 + 1)
    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(413, "Repository archive exceeds 25MB")

    workspace_id = f"repo-{uuid.uuid4().hex[:12]}"
    root = (settings.workspace_dir / workspace_id).resolve()
    root.mkdir(parents=True, exist_ok=False)
    staged: list[tuple[Path, str]] = []
    indexed = 0
    try:
        with zipfile.ZipFile(__import__("io").BytesIO(data)) as archive:
            infos = archive.infolist()
            if len(infos) > 500:
                raise HTTPException(400, "Repository contains too many entries")
            total_size = 0
            for info in infos:
                total_size += info.file_size
                if total_size > 50 * 1024 * 1024:
                    raise HTTPException(400, "Repository uncompressed size exceeds 50MB")
                if ((info.external_attr >> 16) & 0o170000) == 0o120000:
                    raise HTTPException(400, "Symlinks are not allowed in repository archives")
                relative = Path(info.filename)
                if relative.is_absolute() or ".." in relative.parts:
                    raise HTTPException(400, "Unsafe path in repository archive")
                target = safe_join(root, info.filename)
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                if target.suffix.lower() not in {".py", ".js", ".ts", ".tsx", ".jsx", ".md", ".txt", ".json"}:
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
                staged.append((target, relative.as_posix()))
                indexed += 1

        # Stage each repository file into the MCP-owned upload boundary.
        settings.ensure_dirs()
        for source, display_name in staged:
            staged_name = f"{uuid.uuid4().hex}-{source.name}"
            upload_target = settings.upload_dir / staged_name
            shutil.copy2(source, upload_target)
            try:
                result = await call_mcp(
                    "ingest_content",
                    {"file_path": staged_name, "display_name": display_name},
                )
                if not result.get("ok"):
                    raise HTTPException(400, result.get("error", "Repository indexing failed"))
            finally:
                upload_target.unlink(missing_ok=True)

        return {"ok": True, "workspace_id": workspace_id, "files": indexed}
    except HTTPException:
        shutil.rmtree(root, ignore_errors=True)
        raise
    except (zipfile.BadZipFile, OSError, SecurityError) as exc:
        shutil.rmtree(root, ignore_errors=True)
        raise HTTPException(400, f"Invalid repository archive: {exc}") from exc


@router.post("/tasks")
async def create_task(request: TaskRequest):
    try:
        result = await run_coding_task(request.task, request.workspace_id)
    except Exception as exc:
        raise HTTPException(503, str(exc)) from exc
    task_id = str(uuid.uuid4())
    payload = {
        "task_id": task_id,
        "workspace_id": request.workspace_id,
        "plan": result.plan,
        "evidence": result.evidence,
        "diff": result.diff,
        "test": result.test,
        "critique": result.critique,
        "report": result.report,
        "approval_required": True,
        "status": "awaiting_approval",
    }
    TASKS[task_id] = payload
    return payload


@router.get("/tasks/{task_id}")
def get_task(task_id: str):
    task = TASKS.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return task


@router.post("/tasks/{task_id}/approval")
async def approve_task(task_id: str, request: ApprovalRequest):
    task = TASKS.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    if task["status"] != "awaiting_approval":
        raise HTTPException(409, f"Task is already {task['status']}")
    if not request.approved:
        task["status"] = "rejected"
        task["approval_required"] = False
        return {"ok": True, "status": "rejected", "task_id": task_id}

    # Re-run the exact proposed diff inside the sandbox after explicit approval.
    execution = await call_mcp(
        "execute_sandbox",
        {
            "workspace_id": task["workspace_id"],
            "command": "pytest -q",
            "approved": True,
            "preview": False,
            "diff": task["diff"],
        },
    )
    task["approval_required"] = False
    task["test_after_approval"] = execution
    if not execution.get("ok"):
        task["status"] = "approval_failed_tests"
        return {"ok": False, "status": task["status"], "test": execution}

    root = (settings.workspace_dir / task["workspace_id"]).resolve()
    if not root.exists():
        raise HTTPException(404, "Workspace not found")
    files: dict[str, str] = {}
    for p in root.rglob("*.py"):
        if ".sentinelforge" in p.parts:
            continue
        files[p.relative_to(root).as_posix()] = p.read_text(encoding="utf-8", errors="replace")
    try:
        updated = apply_unified_diff(files, task["diff"])
    except SecurityError as exc:
        task["status"] = "blocked"
        raise HTTPException(400, str(exc)) from exc
    for rel, content in updated.items():
        if files.get(rel) != content:
            target = safe_join(root, rel)
            target.write_text(content, encoding="utf-8")
    task["status"] = "approved_applied"
    return {"ok": True, "status": task["status"], "task_id": task_id, "test": execution}
