"""
Normalization and Deduplication Module for StackSignal.

Cleans release markdown, extracts semantic version tags, computes content
hashes for idempotency, and prepares raw documents for storage.
"""

import hashlib
import re
from typing import Any, Dict, Optional
from packaging.version import parse as parse_version, InvalidVersion

# Regex to strip badges, images, and HTML comments
BADGE_RE = re.compile(r"\[!\[.*?\]\(.*?\)\]\(.*?\)", re.DOTALL)
IMAGE_RE = re.compile(r"!\[.*?\]\(.*?\)", re.DOTALL)
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
MULTI_NEWLINE_RE = re.compile(r"\n{3,}")

TAG_VERSION_RE = re.compile(r"[vV]?(\d+(\.\d+)+([a-zA-Z0-9_\-\.\+]+)?)")

def clean_markdown_content(text: str) -> str:
    """Strips noisy badges, markdown image embeds, HTML comments, and collapses blank lines."""
    if not text:
        return ""
    text = BADGE_RE.sub("", text)
    text = IMAGE_RE.sub("", text)
    text = HTML_COMMENT_RE.sub("", text)
    text = MULTI_NEWLINE_RE.sub("\n\n", text)
    return text.strip()

def normalize_version_tag(tag: str) -> str:
    """Extracts and validates a clean semantic version string from a Git tag (e.g. 'v0.109.0' -> '0.109.0')."""
    if not tag:
        return "0.0.0"
    match = TAG_VERSION_RE.search(tag)
    if match:
        v_str = match.group(1)
        try:
            parsed = parse_version(v_str)
            return str(parsed)
        except InvalidVersion:
            return v_str
    return tag.lstrip("vV").strip()

def compute_document_hash(package_name: str, source_type: str, version: Optional[str], content: str) -> str:
    """Generates a deterministic SHA-256 hash to ensure idempotent ingestion."""
    norm_content = " ".join(content.split())
    raw_key = f"{package_name.lower()}:{source_type}:{version or 'none'}:{norm_content}"
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

def is_version_newer_or_equal(candidate_ver: str, pinned_ver: str) -> bool:
    """Checks if candidate_ver >= pinned_ver using packaging.version."""
    try:
        c_v = parse_version(candidate_ver)
        p_v = parse_version(pinned_ver)
        return c_v >= p_v
    except Exception:
        # If comparison fails, include by default to be safe
        return True
