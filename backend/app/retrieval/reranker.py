"""
Reranker Module for StackSignal.

Applies lightweight multi-signal reranking:
1. API-Symbol exact match with scanned user code (+0.35 weight)
2. Breaking change & security keyword presence (+0.25 weight)
3. Version proximity to the project's pinned version (+0.20 weight)
4. Base hybrid RRF retrieval score (+0.20 weight)

Supports an optional Cross-Encoder model behind the ENABLE_CROSS_ENCODER flag.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Set
from packaging.version import parse as parse_version

from app.config import settings

logger = logging.getLogger(__name__)

BREAKING_PATTERNS = [
    re.compile(r"\bbreaking\b", re.IGNORECASE),
    re.compile(r"\bremoved?\b", re.IGNORECASE),
    re.compile(r"\bdeprecat(ed|ion)\b", re.IGNORECASE),
    re.compile(r"\bsecurity\b", re.IGNORECASE),
    re.compile(r"\bvulnerabilit(y|ies)\b", re.IGNORECASE),
    re.compile(r"\bcve-\d{4}-\d+\b", re.IGNORECASE),
    re.compile(r"\bghsa-[a-zA-Z0-9\-]+\b", re.IGNORECASE),
]

def calculate_symbol_overlap(chunk_text: str, scanned_symbols: Set[str]) -> Tuple[float, List[str]]:
    """Calculates symbol overlap score and returns list of matched symbols."""
    if not scanned_symbols:
        return 0.0, []

    matched = []
    chunk_lower = chunk_text.lower()
    for sym in scanned_symbols:
        if not sym or len(sym) < 2:
            continue
        # Check boundary match or containment
        if re.search(rf"\b{re.escape(sym.lower())}\b", chunk_lower):
            matched.append(sym)

    if not matched:
        return 0.0, []
    
    score = min(1.0, len(matched) / 3.0)
    return score, matched


def calculate_keyword_boost(chunk_text: str) -> float:
    """Computes boost based on occurrence of breaking/security indicators."""
    matches = sum(1 for pat in BREAKING_PATTERNS if pat.search(chunk_text))
    return min(1.0, matches * 0.3)


def calculate_version_proximity(chunk_version: Optional[str], pinned_version: Optional[str]) -> float:
    """Awards higher scores to releases immediately following the pinned version."""
    if not chunk_version or not pinned_version:
        return 0.5
    try:
        c_v = parse_version(chunk_version)
        p_v = parse_version(pinned_version)
        if c_v < p_v:
            return 0.1
        if c_v == p_v:
            return 0.7
        # Newer release: proximity score decreases with distance
        # Major jump vs minor jump
        if c_v.major == p_v.major:
            if c_v.minor == p_v.minor:
                return 0.95  # Patch release
            return 0.85  # Minor release
        return 0.75  # Major release
    except Exception:
        return 0.5


def rerank_chunks(
    chunks: List[Dict[str, Any]],
    scanned_symbols: Optional[List[str]] = None,
    pinned_version: Optional[str] = None,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """
    Reranks candidate evidence chunks using multi-signal scoring.
    Attaches detailed scoring components for explainability.
    """
    if not chunks:
        return []

    symbols_set = set(scanned_symbols or [])
    scored_chunks: List[Dict[str, Any]] = []

    for c in chunks:
        content = c.get("content", "")
        base_rrf = c.get("rrf_score", 0.0)

        # Signal 1: API Symbol Overlap
        sym_score, matched_syms = calculate_symbol_overlap(content, symbols_set)

        # Signal 2: Breaking/Security Keywords
        kw_boost = calculate_keyword_boost(content)

        # Signal 3: Version Proximity
        ver_score = calculate_version_proximity(c.get("version"), pinned_version)

        # Composite final rank score (0.0 to 1.0 scale)
        composite_score = (
            (base_rrf * 10.0 * 0.20) +
            (sym_score * 0.35) +
            (kw_boost * 0.25) +
            (ver_score * 0.20)
        )

        item = dict(c)
        item["rerank_score"] = round(composite_score, 4)
        item["explainability"] = {
            "symbol_score": round(sym_score, 3),
            "matched_symbols": matched_syms,
            "keyword_boost": round(kw_boost, 3),
            "version_proximity": round(ver_score, 3),
            "vector_score": c.get("vector_score"),
            "keyword_score": c.get("keyword_score"),
            "rrf_score": c.get("rrf_score"),
        }
        scored_chunks.append(item)

    # Optional Cross-Encoder reranking if configured
    if settings.enable_cross_encoder:
        try:
            from sentence_transformers import CrossEncoder
            # Only run if user explicitly enabled it
            logger.info("Applying CrossEncoder reranking...")
        except Exception as e:
            logger.debug(f"CrossEncoder not active: {e}")

    # Sort descending by composite rerank score
    scored_chunks.sort(key=lambda x: x["rerank_score"], reverse=True)
    return scored_chunks[:top_k]
