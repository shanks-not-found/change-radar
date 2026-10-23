"""
Chunker Module for StackSignal.

Splits release notes and security advisories into semantically coherent passages.
Performs hierarchical splitting:
1. Splits on Markdown headings (e.g. ## Breaking Changes, ### Fixes)
2. Further splits long sections using LangChain RecursiveCharacterTextSplitter with overlap
3. Retains rich metadata on every chunk (package, version, date, URL, source type, section)
"""

import json
import logging
import re
from typing import Any, Dict, List
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.db import get_db

logger = logging.getLogger(__name__)

# Heading regex for markdown releases
HEADING_RE = re.compile(r"^(#{1,4}\s+.*)$", re.MULTILINE)

def split_by_markdown_sections(markdown_text: str) -> List[Tuple[str, str]]:
    """
    Splits markdown into (section_heading, section_body) tuples.
    If no headings are found, returns ('Overview', markdown_text).
    """
    lines = markdown_text.splitlines()
    sections: List[Tuple[str, str]] = []
    
    current_heading = "Overview"
    current_lines: List[str] = []

    for line in lines:
        if line.startswith(("# ", "## ", "### ", "#### ")):
            if current_lines:
                body = "\n".join(current_lines).strip()
                if body:
                    sections.append((current_heading, body))
                current_lines = []
            current_heading = line.lstrip("#").strip()
        else:
            current_lines.append(line)

    if current_lines:
        body = "\n".join(current_lines).strip()
        if body:
            sections.append((current_heading, body))

    if not sections:
        sections.append(("Overview", markdown_text.strip()))

    return sections


def chunk_document(
    doc: Dict[str, Any],
    chunk_size: int = 700,
    chunk_overlap: int = 120,
) -> List[Dict[str, Any]]:
    """
    Chunks a raw document into smaller passages with metadata.
    """
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", "- ", "* ", ". ", " ", ""],
    )

    doc_id = doc["id"]
    pkg = doc["package_name"]
    ver = doc.get("version") or "unknown"
    url = doc["url"]
    pub_date = doc.get("published_at") or ""
    source_type = doc.get("source_type") or "github_release"
    raw_content = doc.get("raw_content") or ""

    sections = split_by_markdown_sections(raw_content)
    chunks: List[Dict[str, Any]] = []
    chunk_index = 0

    for heading, section_text in sections:
        split_texts = text_splitter.split_text(section_text)
        for part in split_texts:
            part_clean = part.strip()
            if not part_clean:
                continue

            chunk_id = f"{doc_id}_c{chunk_index}"
            meta = {
                "chunk_id": chunk_id,
                "document_id": doc_id,
                "package_name": pkg,
                "version": ver,
                "published_at": pub_date,
                "url": url,
                "source_type": source_type,
                "section_heading": heading,
            }

            chunks.append({
                "id": chunk_id,
                "document_id": doc_id,
                "package_name": pkg,
                "version": ver,
                "section_heading": heading,
                "chunk_index": chunk_index,
                "content": part_clean,
                "url": url,
                "published_at": pub_date,
                "metadata": meta,
                "metadata_json": json.dumps(meta),
            })
            chunk_index += 1

    return chunks


def index_chunks_in_db(chunks: List[Dict[str, Any]]) -> int:
    """
    Persists chunks to SQLite 'chunks' and virtual FTS5 'chunks_fts' table.
    Idempotent: updates existing chunks on conflict.
    """
    if not chunks:
        return 0

    with get_db() as conn:
        cursor = conn.cursor()
        for c in chunks:
            # 1. Insert/update in chunks table
            cursor.execute("""
                INSERT INTO chunks (
                    id, document_id, package_name, version, section_heading,
                    chunk_index, content, url, published_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    content = excluded.content,
                    metadata_json = excluded.metadata_json,
                    url = excluded.url;
            """, (
                c["id"],
                c["document_id"],
                c["package_name"],
                c["version"],
                c["section_heading"],
                c["chunk_index"],
                c["content"],
                c["url"],
                c["published_at"],
                c["metadata_json"],
            ))

            # 2. Sync to FTS5 virtual table
            # Check if chunk_id already exists in FTS
            cursor.execute("SELECT rowid FROM chunks_fts WHERE chunk_id = ?", (c["id"],))
            existing_fts = cursor.fetchone()
            if existing_fts:
                cursor.execute("""
                    UPDATE chunks_fts SET
                        package_name = ?,
                        version = ?,
                        section_heading = ?,
                        content = ?
                    WHERE chunk_id = ?;
                """, (
                    c["package_name"],
                    c["version"],
                    c["section_heading"],
                    c["content"],
                    c["id"],
                ))
            else:
                cursor.execute("""
                    INSERT INTO chunks_fts (
                        chunk_id, package_name, version, section_heading, content
                    ) VALUES (?, ?, ?, ?, ?);
                """, (
                    c["id"],
                    c["package_name"],
                    c["version"],
                    c["section_heading"],
                    c["content"],
                ))

    return len(chunks)
