from __future__ import annotations

import logging
from functools import lru_cache

import numpy as np

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_model(model_name: str):
    from sentence_transformers import SentenceTransformer
    logger.info("loading_embedding_model", extra={"model": model_name})
    return SentenceTransformer(model_name)


def embed_texts(texts: list[str], model_name: str) -> np.ndarray:
    model = get_model(model_name)
    vectors = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)
    return np.asarray(vectors, dtype=np.float32)
