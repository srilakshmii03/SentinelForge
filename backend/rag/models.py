from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceRef:
    filename: str
    page: int | None = None
    section: str | None = None
    start_line: int | None = None
    end_line: int | None = None

    def label(self) -> str:
        parts = [self.filename]
        if self.page is not None:
            parts.append(f"page {self.page}")
        if self.section:
            parts.append(f"section {self.section}")
        if self.start_line is not None:
            parts.append(f"lines {self.start_line}-{self.end_line}")
        return " · ".join(parts)


@dataclass(frozen=True)
class Chunk:
    id: str
    document_id: str
    filename: str
    content: str
    source: SourceRef
    content_hash: str
    vector: object | None = None
