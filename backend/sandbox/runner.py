from __future__ import annotations

import subprocess
import tempfile
import threading
import time
from pathlib import Path

from backend.core.config import settings
from backend.security.commands import validate_command
from backend.security.paths import reject_symlink_escape


class SandboxRunner:
    def __init__(self, workspace_root: Path | None = None):
        self.workspace_root = (workspace_root or settings.workspace_dir).resolve()
        self.workspace_root.mkdir(parents=True, exist_ok=True)

    def execute(self, files: dict[str, str], command: str, approved: bool = False, preview: bool = False) -> dict:
        # Preview execution is safe because it occurs in an isolated temporary workspace.
        # Applying a generated patch is a separate, explicit approval boundary.
        if not approved and not preview:
            return {"ok": False, "status": "approval_required", "message": "Sandbox execution requires explicit approval."}
        args = validate_command(command)
        started = time.monotonic()
        with tempfile.TemporaryDirectory(dir=self.workspace_root) as tmp:
            root = Path(tmp).resolve()
            for rel, content in files.items():
                target = reject_symlink_escape(root, rel)
                if target.suffix.lower() not in {".py", ".txt", ".md", ".json"}:
                    return {"ok": False, "status": "blocked", "message": f"File type not allowed: {rel}"}
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")

            cmd = ["docker", "run", "--rm", "--network", "none",
                   "--cpus", "0.5", "--memory", f"{settings.sandbox_memory_mb}m",
                   "--pids-limit", str(settings.sandbox_pids_limit),
                   "--read-only", "--tmpfs", "/tmp:rw,noexec,nosuid,size=32m",
                   "-v", f"{root}:/workspace:rw", "-w", "/workspace",
                   "python:3.12-slim", *args]
            output_limit = settings.sandbox_output_kb * 1024
            streams: dict[str, bytearray] = {"stdout": bytearray(), "stderr": bytearray()}
            overflow = {"value": False}

            def drain(stream, name: str) -> None:
                while True:
                    chunk = stream.read(4096)
                    if not chunk:
                        return
                    if len(streams[name]) < output_limit:
                        streams[name].extend(chunk[: output_limit - len(streams[name])])
                    if len(streams[name]) >= output_limit:
                        overflow["value"] = True
                        return

            try:
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                assert proc.stdout is not None and proc.stderr is not None
                stdout_thread = threading.Thread(target=drain, args=(proc.stdout, "stdout"), daemon=True)
                stderr_thread = threading.Thread(target=drain, args=(proc.stderr, "stderr"), daemon=True)
                stdout_thread.start(); stderr_thread.start()
                deadline = time.monotonic() + settings.sandbox_timeout_seconds
                while proc.poll() is None:
                    if overflow["value"]:
                        proc.kill()
                        proc.wait()
                        return {"ok": False, "status": "output_limit", "stdout": streams["stdout"].decode(errors="replace"), "stderr": streams["stderr"].decode(errors="replace"), "duration_ms": int((time.monotonic()-started)*1000), "network": False}
                    if time.monotonic() >= deadline:
                        proc.kill()
                        proc.wait()
                        return {"ok": False, "status": "timeout", "stdout": streams["stdout"].decode(errors="replace"), "stderr": streams["stderr"].decode(errors="replace"), "duration_ms": int((time.monotonic()-started)*1000), "network": False}
                    time.sleep(0.05)
                stdout_thread.join(timeout=1); stderr_thread.join(timeout=1)
            except OSError as exc:
                return {"ok": False, "status": "runner_error", "error": str(exc), "duration_ms": int((time.monotonic()-started)*1000), "network": False}

            duration = int((time.monotonic() - started) * 1000)
            stdout = streams["stdout"].decode(errors="replace")
            stderr = streams["stderr"].decode(errors="replace")
            return {"ok": proc.returncode == 0, "status": "completed", "exit_code": proc.returncode, "stdout": stdout, "stderr": stderr, "duration_ms": duration, "network": False, "timed_out": False}
