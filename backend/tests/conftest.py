import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
import pytest

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Force mock mode and test databases
os.environ["LLM_PROVIDER"] = "mock"
os.environ["DATABASE_PATH"] = str(backend_dir / "data" / "test_stacksignal.db")
os.environ["CHROMA_PERSIST_DIR"] = str(backend_dir / "data" / "test_chroma")

import app.retrieval.embeddings as embeddings_mod
# Use lightweight deterministic fallback embedding for unit testing (zero model download)
embeddings_mod._EMBEDDING_MODEL_INSTANCE = "fallback"

# Mock fixtures for GitHub releases and OSV advisories
MOCK_RELEASES = {
    "fastapi": [
        {
            "id": "gh_fastapi_0.110.0_mock",
            "package_name": "fastapi",
            "source_type": "github_release",
            "version": "0.110.0",
            "title": "FastAPI 0.110.0",
            "url": "https://github.com/fastapi/fastapi/releases/tag/0.110.0",
            "published_at": "2024-02-24T00:00:00Z",
            "raw_content": "## Breaking Changes\nFastAPI 0.110.0 drops support for older starlette versions. Please upgrade starlette to 0.36.0 or later.",
            "content_hash": "hash_fastapi_01100",
        }
    ],
    "pydantic": [
        {
            "id": "gh_pydantic_2.6.0_mock",
            "package_name": "pydantic",
            "source_type": "github_release",
            "version": "2.6.0",
            "title": "Pydantic 2.6.0",
            "url": "https://github.com/pydantic/pydantic/releases/tag/v2.6.0",
            "published_at": "2024-01-22T00:00:00Z",
            "raw_content": "## Changes\nBaseModel.parse_obj and dict() are deprecated. Use model_validate() and model_dump() instead.",
            "content_hash": "hash_pydantic_260",
        }
    ],
    "langchain": [
        {
            "id": "gh_langchain_0.2.0_mock",
            "package_name": "langchain",
            "source_type": "github_release",
            "version": "0.2.0",
            "title": "LangChain 0.2.0",
            "url": "https://github.com/langchain-ai/langchain/releases/tag/v0.2.0",
            "published_at": "2024-05-15T00:00:00Z",
            "raw_content": "## Breaking Changes\nLLMChain is deprecated in favor of LangChain Expression Language (LCEL) chains.",
            "content_hash": "hash_langchain_020",
        }
    ],
    "chromadb": [
        {
            "id": "gh_chromadb_0.5.0_mock",
            "package_name": "chromadb",
            "source_type": "github_release",
            "version": "0.5.0",
            "title": "ChromaDB 0.5.0",
            "url": "https://github.com/chroma-core/chroma/releases/tag/0.5.0",
            "published_at": "2024-04-10T00:00:00Z",
            "raw_content": "## Changes\nLegacy duckdb+parquet settings have been fully removed in favor of SQLite and HNSW persistence.",
            "content_hash": "hash_chromadb_050",
        }
    ],
    "uvicorn": [
        {
            "id": "gh_uvicorn_0.28.0_mock",
            "package_name": "uvicorn",
            "source_type": "github_release",
            "version": "0.28.0",
            "title": "Uvicorn 0.28.0",
            "url": "https://github.com/encode/uvicorn/releases/tag/0.28.0",
            "published_at": "2024-03-01T00:00:00Z",
            "raw_content": "## Fixes\nImproved worker shutdown handling and WebSocket keepalive.",
            "content_hash": "hash_uvicorn_0280",
        }
    ],
}

MOCK_VULNS = {
    "fastapi": [
        {
            "id": "GHSA-fastapi-mock-1",
            "aliases": ["CVE-2024-24762"],
            "summary": "Form data parsing ReDoS vulnerability in FastAPI",
            "details": "A regular expression denial of service vulnerability exists in multipart form data parsing.",
            "published": "2024-02-05T00:00:00Z",
            "severity": [{"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H"}],
            "affected": [
                {
                    "ranges": [
                        {"type": "ECOSYSTEM", "events": [{"introduced": "0"}, {"fixed": "0.109.1"}]}
                    ]
                }
            ],
            "references": [
                {"type": "ADVISORY", "url": "https://github.com/fastapi/fastapi/security/advisories/GHSA-fastapi-mock-1"}
            ],
        }
    ]
}

@pytest.fixture(autouse=True)
def mock_external_network(monkeypatch):
    """Intercepts external GitHub and OSV network requests during tests."""
    from app.ingestion import github_releases, osv

    def mock_fetch_github_releases(repo_slug: str, package_name: str, pinned_version: Optional[str] = None, max_releases: int = 25):
        pkg = package_name.lower()
        return MOCK_RELEASES.get(pkg, [])

    def mock_query_osv_vulnerabilities(package_name: str, version: Optional[str] = None):
        pkg = package_name.lower()
        return MOCK_VULNS.get(pkg, [])

    monkeypatch.setattr(github_releases, "fetch_github_releases", mock_fetch_github_releases)
    monkeypatch.setattr(osv, "query_osv_vulnerabilities", mock_query_osv_vulnerabilities)
