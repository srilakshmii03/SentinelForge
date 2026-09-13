from __future__ import annotations

import uuid
from pathlib import Path

from .embeddings import embed_texts
from .models import Chunk
from .parsers import parse_file
from .store import VectorStore
from backend.core.config import settings

INJECTION_PATTERNS = (
    "ignore previous instructions",
    "ignore all previous instructions",
    "system prompt",
    "reveal secrets",
    "send the environment",
    "exfiltrate",
)


def sanitize_retrieved_text(text: str) -> tuple[str, bool]:
    lowered = text.lower()
    suspicious = any(pattern in lowered for pattern in INJECTION_PATTERNS)
    if suspicious:
        return "[UNTRUSTED DOCUMENT CONTENT REDACTED FROM INSTRUCTIONAL USE]", True
    return text, False


class RAGPipeline:
    def __init__(self):
        settings.ensure_dirs()
        self.store = VectorStore(settings.data_dir / "sentinelforge.db")

    def ingest_path(self, path: Path, filename: str | None = None) -> dict:
        raw = path.read_bytes()
        doc_hash = self.store.sha256(raw)
        existing = self.store.document_by_hash(doc_hash)
        if existing:
            return {"status": "duplicate", "document_id": existing["id"], "filename": existing["filename"], "chunks": 0}

        parsed = parse_file(path, filename)
        if not parsed:
            return {"status": "empty", "document_id": None, "filename": filename or path.name, "chunks": 0}
        doc_id = str(uuid.uuid4())
        enriched: list[Chunk] = []
        for chunk in parsed:
            content_hash = self.store.sha256(chunk.content)
            enriched.append(Chunk(doc_id, doc_id, chunk.filename, chunk.content, chunk.source, content_hash))
        vectors = embed_texts([c.content for c in enriched], settings.embedding_model)
        self.store.add_document(doc_id, filename or path.name, doc_hash, enriched, vectors)
        return {"status": "indexed", "document_id": doc_id, "filename": filename or path.name, "chunks": len(enriched)}

    def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        vectors = embed_texts([query], settings.embedding_model)
        results = self.store.search(vectors[0], top_k)
        safe = []
        for result in results:
            text, suspicious = sanitize_retrieved_text(result["content"])
            result["content"] = text
            result["prompt_injection_detected"] = suspicious
            safe.append(result)
        return safe

    def delete(self, document_id: str) -> bool:
        return self.store.delete_document(document_id)

    def documents(self) -> list[dict]:
        return self.store.list_documents()

    def stats(self) -> dict:
        return self.store.stats()
