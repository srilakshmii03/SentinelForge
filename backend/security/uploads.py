from __future__ import annotations

from pathlib import Path

ALLOWED_EXTENSIONS = {".pdf", ".md", ".markdown", ".txt", ".json", ".py", ".js", ".ts", ".tsx", ".jsx"}


def validate_filename(filename: str) -> str:
    clean = Path(filename).name
    if clean != filename or filename in {"", ".", ".."}:
        raise ValueError("Unsafe filename")
    if Path(clean).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {Path(clean).suffix}")
    return clean
