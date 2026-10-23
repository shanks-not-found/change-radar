"""
Ingestion Pipeline for StackSignal.

Coordinates external evidence collection for a project's dependencies:
1. Maps packages to official GitHub repositories
2. Fetches release notes via GitHub REST API (with version-window filtering)
3. Queries OSV for security advisories
4. Idempotently stores raw evidence documents in SQLite
"""

import logging
from typing import Any, Dict, List, Tuple

from app.schemas import DependencyInfo
from app.analysis.package_map import resolve_package_metadata
from app.ingestion.github_releases import fetch_github_releases, save_raw_documents
from app.ingestion.osv import fetch_and_store_osv_advisories

logger = logging.getLogger(__name__)

def run_ingestion_for_dependencies(
    dependencies: List[DependencyInfo],
    max_releases_per_pkg: int = 25,
) -> Dict[str, Dict[str, Any]]:
    """
    Runs evidence ingestion for a list of detected dependencies.
    Returns summary dictionary keyed by package name:
    {
      "fastapi": {
         "repo": "fastapi/fastapi",
         "releases_count": 12,
         "advisories_count": 1,
         "documents": [...]
      }
    }
    """
    ingestion_summary: Dict[str, Dict[str, Any]] = {}

    for dep in dependencies:
        pkg = dep.package_name
        pinned = dep.pinned_version
        import_names, repo_slug = resolve_package_metadata(pkg)

        pkg_summary: Dict[str, Any] = {
            "package": pkg,
            "repo": repo_slug,
            "pinned_version": pinned,
            "releases_count": 0,
            "advisories_count": 0,
            "documents": [],
        }

        # 1. Fetch GitHub Releases if mapped repo exists
        if repo_slug:
            try:
                releases = fetch_github_releases(
                    repo_slug=repo_slug,
                    package_name=pkg,
                    pinned_version=pinned,
                    max_releases=max_releases_per_pkg,
                )
                if releases:
                    save_raw_documents(releases)
                    pkg_summary["releases_count"] = len(releases)
                    pkg_summary["documents"].extend(releases)
            except Exception as e:
                logger.warning(f"Error ingesting GitHub releases for {pkg} ({repo_slug}): {e}")

        # 2. Fetch OSV Advisories
        try:
            advisories = fetch_and_store_osv_advisories(pkg, pinned)
            if advisories:
                pkg_summary["advisories_count"] = len(advisories)
                pkg_summary["documents"].extend(advisories)
        except Exception as e:
            logger.warning(f"Error ingesting OSV advisories for {pkg}: {e}")

        ingestion_summary[pkg] = pkg_summary

    return ingestion_summary
