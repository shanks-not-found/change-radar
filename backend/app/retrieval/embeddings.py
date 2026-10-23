"""
Embeddings Module for StackSignal.

Uses ChromaDB's built-in ONNX embedding function (default_ef) which runs
BAAI/bge-small-en-v1.5 via onnxruntime — same model quality as sentence-transformers
but without the PyTorch / CUDA dependency tree (~3.5 GB saved on Vercel).
Provides:
- Batch passage encoding
- Query encoding with the BGE query instruction prefix
- Deterministic fallback for offline/test runs
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
    """Singleton getter for ChromaDB's built-in ONNX embedding function.

    chromadb.utils.embedding_functions.DefaultEmbeddingFunction uses
    onnxruntime to run BAAI/bge-small-en-v1.5 — no torch/CUDA required.
    """
    global _EMBEDDING_MODEL_INSTANCE
    if _EMBEDDING_MODEL_INSTANCE is None:
        try:
            from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
            logger.info("Loading ChromaDB ONNX embedding function (BAAI/bge-small-en-v1.5)...")
            _EMBEDDING_MODEL_INSTANCE = DefaultEmbeddingFunction()
            logger.info("Embedding model loaded successfully.")
        except Exception as e:
            logger.warning(f"Could not load ChromaDB embedding function ({e}). Using deterministic fallback.")
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
    """Encodes a batch of document chunk texts into normalized embedding vectors.

    The DefaultEmbeddingFunction is callable: ef(list_of_texts) -> list of embeddings.
    """
    if not texts:
        return []

    model = get_embedding_model()
    if model == "fallback":
        return [_generate_fallback_embedding(t) for t in texts]

    try:
        # DefaultEmbeddingFunction takes a list and returns a list of float vectors
        embeddings = model(texts)
        return [list(e) for e in embeddings]
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
        embeddings = model([prefixed_query])
        return list(embeddings[0])
    except Exception as e:
        logger.warning(f"Error during query encoding: {e}. Falling back.")
        return _generate_fallback_embedding(prefixed_query)
