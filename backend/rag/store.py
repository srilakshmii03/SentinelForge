from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from typing import Iterable

import numpy as np

from .models import Chunk, SourceRef


class VectorStore:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._init()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self):
        with self._connect() as c:
            c.executescript(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    content_hash TEXT NOT NULL UNIQUE,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    content TEXT NOT NULL,
                    page INTEGER,
                    section TEXT,
                    start_line INTEGER,
                    end_line INTEGER,
                    content_hash TEXT NOT NULL,
                    vector BLOB NOT NULL,
                    FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(document_id);
                CREATE INDEX IF NOT EXISTS idx_chunks_hash ON chunks(content_hash);
                """
            )

    @staticmethod
    def sha256(data: bytes | str) -> str:
        if isinstance(data, str):
            data = data.encode()
        return hashlib.sha256(data).hexdigest()

    def document_by_hash(self, content_hash: str):
        with self._connect() as c:
            return c.execute("SELECT * FROM documents WHERE content_hash=?", (content_hash,)).fetchone()

    def list_documents(self) -> list[dict]:
        with self._connect() as c:
            rows = c.execute("SELECT id, filename, content_hash, created_at FROM documents ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in rows]

    def add_document(self, doc_id: str, filename: str, content_hash: str, chunks: Iterable[Chunk], vectors: np.ndarray):
        chunks = list(chunks)
        with self._connect() as c:
            c.execute("PRAGMA foreign_keys=ON")
            c.execute("INSERT INTO documents(id, filename, content_hash) VALUES(?,?,?)", (doc_id, filename, content_hash))
            for chunk, vector in zip(chunks, vectors):
                cid = hashlib.sha256(f"{doc_id}:{chunk.content_hash}:{chunk.source.start_line}".encode()).hexdigest()
                c.execute(
                    "INSERT INTO chunks(id, document_id, filename, content, page, section, start_line, end_line, content_hash, vector) VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (cid, doc_id, filename, chunk.content, chunk.source.page, chunk.source.section,
                     chunk.source.start_line, chunk.source.end_line, chunk.content_hash,
                     np.asarray(vector, dtype=np.float32).tobytes()),
                )

    def delete_document(self, doc_id: str) -> bool:
        with self._connect() as c:
            c.execute("PRAGMA foreign_keys=ON")
            cur = c.execute("DELETE FROM documents WHERE id=?", (doc_id,))
            return cur.rowcount > 0

    def search(self, query_vector: np.ndarray, top_k: int = 5) -> list[dict]:
        with self._connect() as c:
            rows = c.execute("SELECT * FROM chunks").fetchall()
        if not rows:
            return []
        q = np.asarray(query_vector, dtype=np.float32)
        q_norm = np.linalg.norm(q) or 1.0
        scored = []
        for row in rows:
            v = np.frombuffer(row["vector"], dtype=np.float32)
            score = float(np.dot(v, q) / ((np.linalg.norm(v) or 1.0) * q_norm))
            scored.append((score, row))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                "score": round(score, 4),
                "content": row["content"],
                "source": SourceRef(row["filename"], row["page"], row["section"], row["start_line"], row["end_line"]).__dict__,
                "chunk_id": row["id"],
            }
            for score, row in scored[:top_k]
        ]

    def stats(self) -> dict:
        with self._connect() as c:
            docs = c.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            chunks = c.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        return {"documents": docs, "chunks": chunks}
