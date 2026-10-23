"""
Hybrid Retrieval Module for StackSignal.

Combines Dense Vector Retrieval (ChromaDB) and Sparse Keyword Retrieval (SQLite FTS5)
using Reciprocal Rank Fusion (RRF).
Retains individual channel scores and rank provenance for explainability.
"""

import logging
from typing import Any, Dict, List, Optional
from packaging.version import parse as parse_version

from app.retrieval.vector_store import query_vector_store
from app.retrieval.keyword_store import query_keyword_store
from app.ingestion.normalize import is_version_newer_or_equal

logger = logging.getLogger(__name__)

RRF_K = 60  # Standard smoothing constant for Reciprocal Rank Fusion

def reciprocal_rank_fusion(
    vector_results: List[Dict[str, Any]],
    keyword_results: List[Dict[str, Any]],
    k_constant: int = RRF_K,
) -> List[Dict[str, Any]]:
    """
    Merges vector and keyword search result lists via Reciprocal Rank Fusion.
    Calculates composite RRF score and preserves channel scores.
    """
    # Map chunk_id -> merged dict
    fused: Dict[str, Dict[str, Any]] = {}

    # Process vector rankings (1-indexed)
    for rank, item in enumerate(vector_results, start=1):
        cid = item["chunk_id"]
        if cid not in fused:
            fused[cid] = dict(item)
            fused[cid]["rrf_score"] = 0.0
            fused[cid]["vector_rank"] = None
            fused[cid]["keyword_rank"] = None
            fused[cid]["keyword_score"] = 0.0

        fused[cid]["vector_rank"] = rank
        fused[cid]["vector_score"] = item.get("vector_score", 0.0)
        fused[cid]["rrf_score"] += 1.0 / (k_constant + rank)

    # Process keyword rankings (1-indexed)
    for rank, item in enumerate(keyword_results, start=1):
        cid = item["chunk_id"]
        if cid not in fused:
            fused[cid] = dict(item)
            fused[cid]["rrf_score"] = 0.0
            fused[cid]["vector_rank"] = None
            fused[cid]["keyword_rank"] = None
            fused[cid]["vector_score"] = 0.0

        fused[cid]["keyword_rank"] = rank
        fused[cid]["keyword_score"] = item.get("keyword_score", 0.0)
        fused[cid]["rrf_score"] += 1.0 / (k_constant + rank)

    # Sort descending by rrf_score
    ranked = sorted(fused.values(), key=lambda x: x["rrf_score"], reverse=True)
    return ranked


def hybrid_search(
    query_text: str,
    package_name: Optional[str] = None,
    pinned_version: Optional[str] = None,
    top_k: int = 10,
    candidate_limit: int = 25,
) -> List[Dict[str, Any]]:
    """
    Runs vector and keyword retrieval, fuses rankings, applies version filters,
    and returns top_k evidence chunks.
    """
    # 1. Fetch dense vector results
    try:
        vector_res = query_vector_store(
            query_text=query_text,
            top_k=candidate_limit,
            package_name=package_name,
        )
    except Exception as e:
        logger.warning(f"Vector search failed ({e}). Proceeding with keyword-only.")
        vector_res = []

    # 2. Fetch sparse keyword results
    try:
        keyword_res = query_keyword_store(
            query_text=query_text,
            top_k=candidate_limit,
            package_name=package_name,
        )
    except Exception as e:
        logger.warning(f"Keyword search failed ({e}). Proceeding with vector-only.")
        keyword_res = []

    # 3. Fuse via Reciprocal Rank Fusion
    fused_results = reciprocal_rank_fusion(vector_res, keyword_res)

    # 4. Filter by version if pinned_version is specified
    filtered: List[Dict[str, Any]] = []
    for item in fused_results:
        ver = item.get("version")
        if pinned_version and ver and ver not in ("unknown", "all", "none"):
            try:
                # Keep if ver >= pinned_version
                if not is_version_newer_or_equal(ver, pinned_version):
                    continue
            except Exception:
                pass
        filtered.append(item)

    return filtered[:top_k]


def build_dependency_query(
    package_name: str,
    pinned_version: Optional[str],
    scanned_symbols: List[str],
) -> str:
    """
    Constructs an information-rich query string targeting breaking changes,
    security advisories, and the specific APIs invoked by the project.
    """
    symbols_text = " ".join(scanned_symbols[:8]) if scanned_symbols else ""
    pin_text = f"version {pinned_version}" if pinned_version else ""
    query = f"{package_name} {pin_text} breaking change deprecation removal CVE {symbols_text}"
    return " ".join(query.split())
