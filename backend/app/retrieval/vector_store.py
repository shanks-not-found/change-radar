"""
Vector Store Module for StackSignal using ChromaDB.

Manages persistent local vector embeddings for release note chunks and OSV advisories.
Supports metadata filtering (by package, version, source_type) and cosine distance search.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings
from app.retrieval.embeddings import encode_passages, encode_query

logger = logging.getLogger(__name__)

_CHROMA_CLIENT = None
_COLLECTION = None
COLLECTION_NAME = "stacksignal_evidence_chunks"

def get_chroma_collection():
    """Initializes and returns the persistent ChromaDB collection."""
    global _CHROMA_CLIENT, _COLLECTION
    if _COLLECTION is None:
        try:
            import chromadb
            persist_dir = Path(settings.chroma_persist_dir).resolve()
            persist_dir.mkdir(parents=True, exist_ok=True)
            _CHROMA_CLIENT = chromadb.PersistentClient(path=str(persist_dir))
            _COLLECTION = _CHROMA_CLIENT.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info(f"Connected to ChromaDB at: {persist_dir}")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB collection: {e}")
            raise
    return _COLLECTION


def add_chunks_to_vector_store(chunks: List[Dict[str, Any]]) -> int:
    """
    Computes embeddings for chunks and upserts them into ChromaDB.
    """
    if not chunks:
        return 0

    collection = get_chroma_collection()

    ids = [c["id"] for c in chunks]
    contents = [c["content"] for c in chunks]
    metadatas = []
    for c in chunks:
        meta = {
            "chunk_id": str(c["id"]),
            "document_id": str(c["document_id"]),
            "package_name": str(c["package_name"]).lower(),
            "version": str(c.get("version") or "unknown"),
            "published_at": str(c.get("published_at") or ""),
            "url": str(c.get("url") or ""),
            "section_heading": str(c.get("section_heading") or "General"),
        }
        metadatas.append(meta)

    # Encode passages
    embeddings = encode_passages(contents)

    # Upsert to ChromaDB in batches
    batch_size = 100
    for i in range(0, len(ids), batch_size):
        end = i + batch_size
        collection.upsert(
            ids=ids[i:end],
            embeddings=embeddings[i:end],
            documents=contents[i:end],
            metadatas=metadatas[i:end],
        )

    logger.info(f"Upserted {len(chunks)} chunks into ChromaDB.")
    return len(chunks)


def query_vector_store(
    query_text: str,
    top_k: int = 15,
    package_name: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Searches ChromaDB using cosine similarity.
    Returns normalized list of retrieved chunk matches with vector_score.
    """
    collection = get_chroma_collection()
    query_embedding = encode_query(query_text)

    where_filter = None
    if package_name:
        where_filter = {"package_name": package_name.lower()}

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where=where_filter,
        include=["documents", "metadatas", "distances"],
    )

    matches: List[Dict[str, Any]] = []
    if not results or not results.get("ids") or not results["ids"][0]:
        return matches

    ids = results["ids"][0]
    docs = results["documents"][0]
    metas = results["metadatas"][0]
    distances = results["distances"][0]

    for c_id, content, meta, dist in zip(ids, docs, metas, distances):
        # In cosine distance: 0 is exact match, 2 is opposite.
        # Convert to similarity score between 0.0 and 1.0
        similarity = max(0.0, min(1.0, 1.0 - (dist / 2.0)))
        
        match_item = dict(meta)
        match_item["id"] = c_id
        match_item["chunk_id"] = c_id
        match_item["content"] = content
        match_item["vector_score"] = similarity
        matches.append(match_item)

    return matches
