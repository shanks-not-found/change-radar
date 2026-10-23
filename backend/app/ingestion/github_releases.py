"""
GitHub Releases Ingestion Module for StackSignal.

Fetches GitHub releases via the GitHub REST API with:
- Optional GITHUB_TOKEN authentication (higher rate limits)
- ETag / HTTP caching
- Semantic version filtering around pinned project dependencies
- Graceful fallback on network or rate limit errors
"""

import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple
import httpx
from packaging.version import parse as parse_version

from app.config import settings
from app.db import get_db
from app.ingestion.normalize import (
    clean_markdown_content,
    normalize_version_tag,
    compute_document_hash,
    is_version_newer_or_equal,
)

logger = logging.getLogger(__name__)

# In-memory ETag cache: repo_slug -> (etag, releases_json)
_ETAG_CACHE: Dict[str, Tuple[str, List[Dict[str, Any]]]] = {}

def fetch_github_releases(
    repo_slug: str,
    package_name: str,
    pinned_version: Optional[str] = None,
    max_releases: int = 25,
) -> List[Dict[str, Any]]:
    """
    Fetches releases from GitHub REST API for a repository.
    Filters to releases newer than or equal to pinned_version if specified.
    Returns normalized document dictionaries.
    """
    owner, repo = repo_slug.split("/", 1)
    url = f"https://api.github.com/repos/{owner}/{repo}/releases"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "StackSignal-Analyzer",
    }
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"

    cached_etag, cached_data = _ETAG_CACHE.get(repo_slug, (None, []))
    if cached_etag:
        headers["If-None-Match"] = cached_etag

    releases_raw: List[Dict[str, Any]] = []

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, params={"per_page": min(max_releases, 50)}, headers=headers)
            if resp.status_code == 304 and cached_data:
                logger.info(f"Using ETag cached releases for {repo_slug}")
                releases_raw = cached_data
            elif resp.status_code == 200:
                releases_raw = resp.json()
                new_etag = resp.headers.get("ETag")
                if new_etag:
                    _ETAG_CACHE[repo_slug] = (new_etag, releases_raw)
            elif resp.status_code in (403, 429):
                logger.warning(f"GitHub API rate limit exceeded for {repo_slug}. Returning available local cache.")
                if cached_data:
                    releases_raw = cached_data
            else:
                logger.warning(f"GitHub API returned {resp.status_code} for {repo_slug}: {resp.text[:150]}")
                if cached_data:
                    releases_raw = cached_data
    except Exception as e:
        logger.warning(f"Failed to fetch GitHub releases for {repo_slug}: {e}")
        if cached_data:
            releases_raw = cached_data

    documents: List[Dict[str, Any]] = []

    for rel in releases_raw:
        tag_name = rel.get("tag_name") or rel.get("name") or ""
        body = rel.get("body") or ""
        html_url = rel.get("html_url") or f"https://github.com/{repo_slug}/releases"
        published_at = rel.get("published_at") or rel.get("created_at") or ""
        title = rel.get("name") or tag_name or "Release"

        norm_ver = normalize_version_tag(tag_name)
        cleaned_body = clean_markdown_content(body)
        if not cleaned_body:
            cleaned_body = f"Release {tag_name} for {package_name}."

        # Version window filtering: only keep releases >= pinned_version (or if pinned_version is not set)
        if pinned_version:
            try:
                if not is_version_newer_or_equal(norm_ver, pinned_version):
                    # Also keep the exact pinned version if present
                    if norm_ver != pinned_version:
                        continue
            except Exception:
                pass

        content_hash = compute_document_hash(package_name, "github_release", norm_ver, cleaned_body)
        doc_id = f"gh_{package_name}_{norm_ver}_{content_hash[:8]}"

        doc = {
            "id": doc_id,
            "package_name": package_name.lower(),
            "source_type": "github_release",
            "version": norm_ver,
            "title": title,
            "url": html_url,
            "published_at": published_at,
            "raw_content": cleaned_body,
            "content_hash": content_hash,
        }
        documents.append(doc)

    return documents


def save_raw_documents(documents: List[Dict[str, Any]]) -> int:
    """Idempotently saves documents to SQLite raw_documents table."""
    if not documents:
        return 0

    inserted_count = 0
    with get_db() as conn:
        cursor = conn.cursor()
        for doc in documents:
            doc_id = doc["id"]
            pkg = doc["package_name"]
            src_type = doc.get("source_type", "github_release")
            ver = doc.get("version")
            title = doc.get("title") or doc.get("id") or "Release"
            url = doc.get("url", "")
            pub = doc.get("published_at", "")
            raw = doc.get("raw_content", "")
            chash = doc.get("content_hash") or compute_document_hash(pkg, src_type, ver, raw)

            cursor.execute("""
                INSERT INTO raw_documents (
                    id, package_name, source_type, version, title, url,
                    published_at, raw_content, content_hash, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(content_hash) DO UPDATE SET
                    url = excluded.url,
                    title = excluded.title,
                    published_at = excluded.published_at;
            """, (
                doc_id,
                pkg,
                src_type,
                ver,
                title,
                url,
                pub,
                raw,
                chash,
            ))
            inserted_count += 1

    return inserted_count
