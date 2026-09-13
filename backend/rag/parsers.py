from __future__ import annotations

import json
from pathlib import Path

from pypdf import PdfReader

from .models import Chunk, SourceRef


def _chunk_lines(text: str, max_chars: int = 1800, overlap_lines: int = 2):
    lines = text.splitlines()
    if not lines:
        return []
    out = []
    start = 0
    while start < len(lines):
        chars = 0
        end = start
        while end < len(lines) and (chars + len(lines[end]) + 1 <= max_chars or end == start):
            chars += len(lines[end]) + 1
            end += 1
        out.append((start + 1, end, "\n".join(lines[start:end])))
        if end >= len(lines):
            break
        start = max(start + 1, end - overlap_lines)
    return out


def parse_file(path: Path, display_name: str | None = None) -> list[Chunk]:
    name = display_name or path.name
    suffix = path.suffix.lower()
    chunks: list[Chunk] = []

    if suffix == ".pdf":
        reader = PdfReader(str(path))
        for page_no, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            for start, end, content in _chunk_lines(text):
                chunks.append(Chunk("", "", name, content, SourceRef(name, page=page_no, start_line=start, end_line=end), ""))
        return chunks

    text = path.read_text(encoding="utf-8", errors="replace")
    if suffix == ".json":
        try:
            text = json.dumps(json.loads(text), indent=2, ensure_ascii=False)
        except json.JSONDecodeError:
            pass

    section = None
    for start, end, content in _chunk_lines(text):
        for line in content.splitlines():
            if line.startswith("#"):
                section = line.lstrip("#").strip()
                break
        chunks.append(Chunk("", "", name, content, SourceRef(name, section=section, start_line=start, end_line=end), ""))
    return chunks
