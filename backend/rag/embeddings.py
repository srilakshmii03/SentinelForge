from __future__ import annotations

import hashlib
import logging
import os
from functools import lru_cache

import numpy as np

logger = logging.getLogger(__name__)

EMBEDDING_DIMENSION = 384
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "sentence-transformers").lower()


def _hash_embedding(text: str) -> np.ndarray:
    """
    Lightweight deterministic embedding used for memory-constrained deployments.

    It uses feature hashing over words and word pairs, then L2-normalizes
    the resulting vector so it can be compared with cosine similarity.
    """
    vector = np.zeros(EMBEDDING_DIMENSION, dtype=np.float32)

    tokens = text.lower().split()

    features = tokens[:]

    # Add simple word-pair features to preserve some local context.
    features.extend(
        f"{tokens[i]}_{tokens[i + 1]}"
        for i in range(len(tokens) - 1)
    )

    for feature in features:
        digest = hashlib.sha256(feature.encode("utf-8")).digest()

        index = int.from_bytes(digest[:4], "little") % EMBEDDING_DIMENSION

        # Use another hash bit to distribute positive/negative values.
        sign = 1.0 if digest[4] % 2 == 0 else -1.0

        vector[index] += sign

    norm = np.linalg.norm(vector)

    if norm > 0:
        vector /= norm

    return vector


@lru_cache(maxsize=1)
def get_model(model_name: str):
    if EMBEDDING_PROVIDER == "hash":
        logger.info("Using lightweight hash embeddings")
        return None

    from sentence_transformers import SentenceTransformer

    logger.info(
        "Loading embedding model",
        extra={"model": model_name},
    )

    return SentenceTransformer(model_name)


def embed_texts(texts: list[str], model_name: str) -> np.ndarray:
    if EMBEDDING_PROVIDER == "hash":
        logger.info(
            "Embedding texts with lightweight hash embeddings",
            extra={"count": len(texts)},
        )

        return np.asarray(
            [_hash_embedding(text) for text in texts],
            dtype=np.float32,
        )

    model = get_model(model_name)

    vectors = model.encode(
        texts,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )

    return np.asarray(vectors, dtype=np.float32)
