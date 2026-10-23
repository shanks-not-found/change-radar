"""
Project Loader for StackSignal.

Handles ZIP file uploads and GitHub repository URL downloads.
Enforces security constraints:
- Zip-slip path traversal prevention
- File size caps
- Exclusion of virtual environments, git internals, and node_modules
"""

import io
import logging
import os
import re
import shutil
import uuid
import zipfile
from pathlib import Path
from typing import Optional, Tuple
import httpx

from app.config import settings

logger = logging.getLogger(__name__)

IGNORED_PATH_SEGMENTS = {
    "__pycache__",
    ".git",
    ".venv",
    "venv",
    "node_modules",
    ".idea",
    ".vscode",
    ".pytest_cache",
    ".mypy_cache",
}

def is_safe_zip_member(member_name: str, target_dir: Path) -> bool:
    """Verifies that a zip member does not attempt directory traversal (Zip-Slip)."""
    # Reject absolute paths or paths with '..'
    if member_name.startswith(("/", "\\")) or ".." in member_name.split("/"):
        return False
    resolved = (target_dir / member_name).resolve()
    return resolved.is_relative_to(target_dir.resolve())

def extract_safe_zip(zip_bytes: bytes, destination: Path) -> Path:
    """Extracts a ZIP archive while enforcing path safety and omitting unnecessary folders."""
    destination.mkdir(parents=True, exist_ok=True)
    
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        members = zf.infolist()
        
        # Check if archive has a single top-level folder
        top_dirs = {m.filename.split("/")[0] for m in members if "/" in m.filename}
        single_root = len(top_dirs) == 1 and all(m.filename.startswith(list(top_dirs)[0] + "/") or m.filename == list(top_dirs)[0] for m in members)

        for member in members:
            # Check for zip slip
            if not is_safe_zip_member(member.filename, destination):
                logger.warning(f"Skipping dangerous zip path: {member.filename}")
                continue

            # Skip ignored directories
            parts = Path(member.filename).parts
            if any(part in IGNORED_PATH_SEGMENTS for part in parts):
                continue

            zf.extract(member, destination)

    # If all contents were nested in a single top-level folder (common for github zipballs),
    # return that inner folder if it contains project files
    if single_root and top_dirs:
        nested = destination / list(top_dirs)[0]
        if nested.is_dir():
            return nested

    return destination

def load_from_zip(zip_bytes: bytes, original_filename: str) -> Tuple[str, str, Path]:
    """
    Validates and extracts an uploaded ZIP file.
    Returns (project_id, project_name, project_path).
    """
    if len(zip_bytes) > settings.max_upload_size_bytes:
        raise ValueError(
            f"Uploaded ZIP file exceeds maximum size limit of {settings.max_upload_size_bytes // (1024 * 1024)}MB"
        )

    project_id = str(uuid.uuid4())
    name = Path(original_filename).stem or "uploaded_project"
    target_dir = Path(settings.database_path).parent / "projects" / project_id
    target_dir.mkdir(parents=True, exist_ok=True)

    extracted_root = extract_safe_zip(zip_bytes, target_dir)
    return project_id, name, extracted_root

def parse_github_url(repo_url: str) -> Tuple[str, str]:
    """Parses owner and repository name from a GitHub URL."""
    cleaned = repo_url.strip().rstrip("/")
    match = re.search(r"github\.com/([a-zA-Z0-9_\-\.]+)/([a-zA-Z0-9_\-\.]+)", cleaned)
    if not match:
        raise ValueError(f"Invalid GitHub repository URL: {repo_url}")
    return match.group(1), match.group(2).rstrip(".git")

def load_from_github(repo_url: str) -> Tuple[str, str, Path]:
    """
    Downloads a public repository zipball via GitHub API and extracts it.
    Returns (project_id, project_name, project_path).
    """
    owner, repo = parse_github_url(repo_url)
    project_id = str(uuid.uuid4())
    project_name = repo
    target_dir = Path(settings.database_path).parent / "projects" / project_id
    target_dir.mkdir(parents=True, exist_ok=True)

    download_url = f"https://api.github.com/repos/{owner}/{repo}/zipball"
    headers = {"User-Agent": "StackSignal-Analyzer"}
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"

    with httpx.Client(follow_redirects=True, timeout=30.0) as client:
        resp = client.get(download_url, headers=headers)
        if resp.status_code != 200:
            raise RuntimeError(
                f"Failed to download repository from GitHub ({resp.status_code}): {resp.text[:200]}"
            )
        zip_bytes = resp.content

    if len(zip_bytes) > settings.max_upload_size_bytes:
        raise ValueError(f"Repository archive exceeds maximum size limit of {settings.max_upload_size_bytes // (1024 * 1024)}MB")

    extracted_root = extract_safe_zip(zip_bytes, target_dir)
    return project_id, project_name, extracted_root
