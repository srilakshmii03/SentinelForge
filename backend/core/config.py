from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "development")
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    data_dir: Path = Path(os.getenv("DATA_DIR", "./data"))
    workspace_dir: Path = Path(os.getenv("WORKSPACE_DIR", "./workspaces"))
    upload_dir: Path = Path(os.getenv("UPLOAD_DIR", "./data/uploads"))
    model_provider: str = os.getenv("MODEL_PROVIDER", "ollama")
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "10"))
    sandbox_timeout_seconds: int = int(os.getenv("SANDBOX_TIMEOUT_SECONDS", "20"))
    sandbox_memory_mb: int = int(os.getenv("SANDBOX_MEMORY_MB", "256"))
    sandbox_pids_limit: int = int(os.getenv("SANDBOX_PIDS_LIMIT", "64"))
    sandbox_output_kb: int = int(os.getenv("SANDBOX_OUTPUT_KB", "128"))
    cors_origins: tuple[str, ...] = tuple(
        x.strip() for x in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if x.strip()
    )

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
