"""
Embeddings Module for StackSignal.

Loads sentence-transformers model (default: BAAI/bge-small-en-v1.5) as a singleton.
Provides:
- Batch passage encoding
- Query encoding with the required BGE instruction prefix
- In-memory caching to avoid re-embedding unchanged text
- Fallback mock embedding generator for testing and offline runs
"""

import hashlib
import logging
from typing import List, Optional
import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)

BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

_EMBEDDING_MODEL_INSTANCE = None
_EMBEDDING_CACHE = {}

def get_embedding_model():
    """Singleton getter for the sentence-transformers model."""
    global _EMBEDDING_MODEL_INSTANCE
    if _EMBEDDING_MODEL_INSTANCE is None:
        try:
            from sentence_transformers import SentenceTransformer
            model_name = settings.embedding_model or "BAAI/bge-small-en-v1.5"
            logger.info(f"Loading embedding model: {model_name}...")
            _EMBEDDING_MODEL_INSTANCE = SentenceTransformer(model_name)
            logger.info("Embedding model loaded successfully.")
        except Exception as e:
            logger.warning(f"Could not load SentenceTransformer model ({e}). Using deterministic embedding fallback.")
            _EMBEDDING_MODEL_INSTANCE = "fallback"
    return _EMBEDDING_MODEL_INSTANCE


def _generate_fallback_embedding(text: str, dim: int = 384) -> List[float]:
    """
    Deterministic pseudo-embedding for testing and offline development
    when transformer weights are unavailable.
    """
    h = hashlib.sha256(text.encode("utf-8")).digest()
    # Expand 32 bytes to 384 floats using deterministic PRNG seeded by hash
    seed = int.from_bytes(h[:4], "big")
    rng = np.random.RandomState(seed)
    vec = rng.randn(dim).astype(np.float32)
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec.tolist()


def encode_passages(texts: List[str], batch_size: int = 32) -> List[List[float]]:
    """Encodes a batch of document chunk texts into normalized embedding vectors."""
    if not texts:
        return []

    model = get_embedding_model()
    if model == "fallback":
        return [_generate_fallback_embedding(t) for t in texts]

    try:
        embeddings = model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return embeddings.tolist()
    except Exception as e:
        logger.warning(f"Error during passage encoding: {e}. Falling back.")
        return [_generate_fallback_embedding(t) for t in texts]


def encode_query(query: str) -> List[float]:
    """Encodes a search query with the BGE query instruction prefix."""
    prefixed_query = f"{BGE_QUERY_PREFIX}{query.strip()}"
    model = get_embedding_model()
    if model == "fallback":
        return _generate_fallback_embedding(prefixed_query)

    try:
        embedding = model.encode(
            prefixed_query,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return embedding.tolist()
    except Exception as e:
        logger.warning(f"Error during query encoding: {e}. Falling back.")
        return _generate_fallback_embedding(prefixed_query)
