"""
OSV (Open Source Vulnerabilities) API Ingestion Module for StackSignal.

Queries https://api.osv.dev/v1/query for package vulnerabilities on PyPI.
Extracts CVEs, GHSA IDs, severity, affected versions, fixed versions, and advisory links.
Persists normalized advisories into SQLite idempotently.
"""

import logging
from typing import Any, Dict, List, Optional
import httpx

from app.ingestion.normalize import (
    clean_markdown_content,
    compute_document_hash,
)
from app.ingestion.github_releases import save_raw_documents

logger = logging.getLogger(__name__)

OSV_QUERY_URL = "https://api.osv.dev/v1/query"
OSV_BATCH_URL = "https://api.osv.dev/v1/querybatch"

# In-memory advisory cache: f"{pkg}:{version}" -> raw_vulns_list
_OSV_CACHE: Dict[str, List[Dict[str, Any]]] = {}

def query_osv_vulnerabilities(package_name: str, version: Optional[str] = None) -> List[Dict[str, Any]]:
    """Queries OSV API for vulnerabilities affecting a specific PyPI package and version."""
    pkg = package_name.lower()
    cache_key = f"{pkg}:{version or 'all'}"
    if cache_key in _OSV_CACHE:
        return _OSV_CACHE[cache_key]

    payload: Dict[str, Any] = {
        "package": {
            "name": pkg,
            "ecosystem": "PyPI",
        }
    }
    if version:
        payload["version"] = version

    vulns: List[Dict[str, Any]] = []

    try:
        with httpx.Client(timeout=8.0) as client:
            resp = client.post(OSV_QUERY_URL, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                vulns = data.get("vulns", [])
            else:
                logger.warning(f"OSV API returned status {resp.status_code} for {pkg}: {resp.text[:100]}")
    except Exception as e:
        logger.warning(f"OSV API query failed for {pkg} (version {version}): {e}")

    _OSV_CACHE[cache_key] = vulns
    return vulns


def parse_and_normalize_osv_advisory(vuln: Dict[str, Any], package_name: str, pinned_version: Optional[str]) -> Dict[str, Any]:
    """Transforms raw OSV vulnerability payload into normalized document schema."""
    adv_id = vuln.get("id", "UNKNOWN-ADV")
    aliases = vuln.get("aliases", [])
    alias_str = f" ({', '.join(aliases)})" if aliases else ""
    summary = vuln.get("summary") or f"Security advisory for {package_name} {adv_id}"
    details = vuln.get("details") or ""
    published = vuln.get("published") or ""

    # Severity extraction
    severities = vuln.get("severity", [])
    sev_str = "UNKNOWN"
    if isinstance(severities, list) and severities:
        sev_str = severities[0].get("score", severities[0].get("type", "UNKNOWN"))

    # Extract fixed versions & references
    fixed_versions: List[str] = []
    affected_ranges: List[str] = []
    for affected in vuln.get("affected", []):
        for r in affected.get("ranges", []):
            range_type = r.get("type", "")
            events = r.get("events", [])
            for ev in events:
                if "fixed" in ev:
                    fixed_versions.append(ev["fixed"])
                elif "introduced" in ev:
                    affected_ranges.append(f">={ev['introduced']}")

    refs = vuln.get("references", [])
    primary_url = f"https://osv.dev/vulnerability/{adv_id}"
    for ref in refs:
        if ref.get("type") in ("ADVISORY", "WEB", "REPORT"):
            primary_url = ref.get("url", primary_url)
            break

    fixed_info = f"Fixed in: {', '.join(fixed_versions)}" if fixed_versions else "No fixed version specified."
    content = (
        f"Security Advisory: {adv_id}{alias_str}\n"
        f"Package: {package_name} (PyPI)\n"
        f"Severity: {sev_str}\n"
        f"{fixed_info}\n\n"
        f"Summary: {summary}\n\n"
        f"Details:\n{details.strip()}"
    )

    cleaned_content = clean_markdown_content(content)
    ver = pinned_version or "all"
    content_hash = compute_document_hash(package_name, "osv_advisory", adv_id, cleaned_content)

    return {
        "id": f"osv_{package_name}_{adv_id}",
        "package_name": package_name.lower(),
        "source_type": "osv_advisory",
        "version": ver,
        "title": f"[{adv_id}] {summary[:120]}",
        "url": primary_url,
        "published_at": published,
        "raw_content": cleaned_content,
        "content_hash": content_hash,
    }


def fetch_and_store_osv_advisories(package_name: str, version: Optional[str] = None) -> List[Dict[str, Any]]:
    """Queries OSV, normalizes returned advisories, and persists them into SQLite raw_documents."""
    raw_vulns = query_osv_vulnerabilities(package_name, version)
    docs = [
        parse_and_normalize_osv_advisory(v, package_name, version)
        for v in raw_vulns
    ]
    if docs:
        save_raw_documents(docs)
    return docs
