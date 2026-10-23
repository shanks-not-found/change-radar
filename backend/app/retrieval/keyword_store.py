"""
Keyword Store Module for StackSignal using SQLite FTS5.

Provides fast, exact BM25 keyword matching for API symbols, error messages,
CVE numbers, and package names.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from app.db import get_db

logger = logging.getLogger(__name__)

# Characters requiring escaping in SQLite FTS5
FTS5_SPECIAL_CHARS = re.compile(r'["\*\+\-\^\:]')

def clean_fts5_query(query: str) -> str:
    """Cleans and formats a query string for safe SQLite FTS5 MATCH evaluation."""
    # Remove special punctuation
    words = [w.strip() for w in re.split(r"[^a-zA-Z0-9_\.]+", query) if len(w.strip()) > 1]
    if not words:
        return '""'
    # Use OR to match any of the salient terms or symbols
    escaped_words = [f'"{w}"' for w in words]
    return " OR ".join(escaped_words)

def query_keyword_store(
    query_text: str,
    top_k: int = 15,
    package_name: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Executes a BM25 keyword search on chunks_fts virtual table.
    Returns ranked chunk records with keyword_score.
    """
    clean_query = clean_fts5_query(query_text)
    if clean_query == '""':
        return []

    sql = """
        SELECT
            c.id,
            c.document_id,
            c.package_name,
            c.version,
            c.section_heading,
            c.content,
            c.url,
            c.published_at,
            c.metadata_json,
            bm25(chunks_fts) AS bm25_score
        FROM chunks_fts
        JOIN chunks c ON c.id = chunks_fts.chunk_id
        WHERE chunks_fts MATCH ?
    """
    params: List[Any] = [clean_query]

    if package_name:
        sql += " AND c.package_name = ?"
        params.append(package_name.lower())

    sql += " ORDER BY bm25_score ASC LIMIT ?"
    params.append(top_k)

    matches: List[Dict[str, Any]] = []
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            rows = cursor.fetchall()

            for row in rows:
                raw_bm25 = row["bm25_score"]  # In SQLite, negative values represent closer matches
                # Normalize BM25 score into positive range [0, 1]
                # Typically -10.0 to 0.0 -> map to [0.2, 1.0]
                normalized_score = 1.0 / (1.0 + max(0.0, raw_bm25 + 5.0) if raw_bm25 >= 0 else 1.0 / (1.0 + abs(raw_bm25)))

                meta = {}
                if row["metadata_json"]:
                    try:
                        meta = json.loads(row["metadata_json"])
                    except Exception:
                        pass

                item = dict(meta)
                item["id"] = row["id"]
                item["chunk_id"] = row["id"]
                item["document_id"] = row["document_id"]
                item["package_name"] = row["package_name"]
                item["version"] = row["version"]
                item["section_heading"] = row["section_heading"]
                item["content"] = row["content"]
                item["url"] = row["url"]
                item["published_at"] = row["published_at"]
                item["keyword_score"] = round(float(normalized_score), 4)
                item["bm25_raw"] = float(raw_bm25)
                matches.append(item)
    except Exception as e:
        logger.warning(f"FTS5 keyword search error for '{clean_query}': {e}")

    return matches
