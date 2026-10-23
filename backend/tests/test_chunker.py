import pytest
from app.db import init_db, get_db
from app.retrieval.chunker import (
    split_by_markdown_sections,
    chunk_document,
    index_chunks_in_db,
)

@pytest.fixture(autouse=True)
def setup_database():
    init_db()

def test_split_by_markdown_sections():
    md = """# Release 2.0.0

## Breaking Changes
- Removed old parse_obj method
- Deprecated dict() in favor of model_dump()

## Features
- Added strict mode validation
"""
    sections = split_by_markdown_sections(md)
    headings = [s[0] for s in sections]

    assert "Breaking Changes" in headings
    assert "Features" in headings

def test_chunk_document():
    doc = {
        "id": "doc_fastapi_1",
        "package_name": "fastapi",
        "version": "0.110.0",
        "url": "https://github.com/fastapi/fastapi/releases/tag/0.110.0",
        "published_at": "2024-02-24T00:00:00Z",
        "source_type": "github_release",
        "raw_content": """## Breaking Changes
FastAPI 0.110.0 drops support for older starlette versions.
Please upgrade starlette to 0.36.0 or later.

## Fixes
Fix route resolution in sub-applications with trailing slashes.
""",
    }

    chunks = chunk_document(doc, chunk_size=200, chunk_overlap=20)
    assert len(chunks) >= 2
    assert all("chunk_id" in c["metadata"] for c in chunks)
    assert all(c["package_name"] == "fastapi" for c in chunks)
    assert any("Breaking Changes" in c["section_heading"] for c in chunks)

from app.ingestion.github_releases import save_raw_documents
from app.ingestion.normalize import compute_document_hash

def test_index_chunks_in_db():
    content = "## Changes\nRemoved BaseModel.parse_obj and replaced with model_validate."
    doc = {
        "id": "doc_test_1",
        "package_name": "pydantic",
        "version": "2.0.0",
        "title": "Pydantic 2.0.0",
        "url": "https://github.com/pydantic/pydantic/releases",
        "published_at": "2023-06-30",
        "source_type": "github_release",
        "raw_content": content,
        "content_hash": compute_document_hash("pydantic", "github_release", "2.0.0", content),
    }
    save_raw_documents([doc])
    chunks = chunk_document(doc)
    count = index_chunks_in_db(chunks)
    assert count == len(chunks)

    # Verify queryable in FTS5
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM chunks_fts WHERE chunks_fts MATCH 'parse_obj';")
        rows = cursor.fetchall()
        assert len(rows) >= 1
