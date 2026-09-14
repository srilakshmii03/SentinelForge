from __future__ import annotations

import contextlib
import time
import uuid
import shutil
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.routing import Mount
from mcp.server.transport_security import TransportSecuritySettings

from backend.api.routes import router
from backend.core.config import settings
from backend.core.logging import configure_logging
from backend.mcp.server import mcp

configure_logging()
settings.ensure_dirs()

# Bootstrap synthetic demo data on each process start. This is safe for ephemeral hosts.
def bootstrap_demo_workspace() -> None:
    target = settings.workspace_dir / "demo"
    source = Path("sample-data")
    if source.exists() and not target.exists():
        shutil.copytree(source, target)

bootstrap_demo_workspace()

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    async with mcp.session_manager.run():
        yield

app = FastAPI(title="SentinelForge API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Accept", "Mcp-Session-Id", "Mcp-Protocol-Version"],
    expose_headers=["Mcp-Session-Id"],
)

@app.middleware("http")
async def request_context(request: Request, call_next):
    rid = str(uuid.uuid4())
    started = time.monotonic()
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    response.headers["X-Response-Time-Ms"] = str(int((time.monotonic() - started) * 1000))
    return response

app.include_router(router)
mcp_security = TransportSecuritySettings(
    allowed_hosts=[
        "localhost",
        "127.0.0.1",
        "sentinelforge-app.onrender.com",
    ],
    allowed_origins=[
        "http://localhost:5173",
        "https://sentinelforge-app.onrender.com",
    ],
)

app.mount(
    "/mcp",
    mcp.streamable_http_app(
        streamable_http_path="/",
        transport_security=mcp_security,
    ),
)

@app.get("/")
def root():
    index = Path("frontend/dist/index.html")
    if index.exists():
        return FileResponse(index)
    return {"name": "SentinelForge", "status": "running", "docs": "/docs", "mcp": "/mcp"}


# Serve the production frontend when it is present in the container. API/MCP routes remain mounted above it.
from fastapi.staticfiles import StaticFiles

frontend_dist = Path("frontend/dist")
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="frontend-assets")
