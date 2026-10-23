"""
Package Map for StackSignal.

Maps PyPI package names to their Python import module names and GitHub repositories.
Includes a rich built-in dictionary for core packages and an HTTP fallback to
the PyPI JSON API for unlisted libraries.
"""

import logging
import re
from typing import Dict, List, Optional, Tuple
import httpx

logger = logging.getLogger(__name__)

# Core mapping: (pypi_name) -> { "import_names": [...], "repo": "owner/repo" }
KNOWN_PACKAGES: Dict[str, Dict[str, Any]] = {
    "fastapi": {
        "import_names": ["fastapi"],
        "repo": "fastapi/fastapi",
        "github_url": "https://github.com/fastapi/fastapi",
    },
    "starlette": {
        "import_names": ["starlette"],
        "repo": "encode/starlette",
        "github_url": "https://github.com/encode/starlette",
    },
    "pydantic": {
        "import_names": ["pydantic", "pydantic_core"],
        "repo": "pydantic/pydantic",
        "github_url": "https://github.com/pydantic/pydantic",
    },
    "langchain": {
        "import_names": ["langchain"],
        "repo": "langchain-ai/langchain",
        "github_url": "https://github.com/langchain-ai/langchain",
    },
    "langchain-core": {
        "import_names": ["langchain_core"],
        "repo": "langchain-ai/langchain",
        "github_url": "https://github.com/langchain-ai/langchain",
    },
    "langchain-community": {
        "import_names": ["langchain_community"],
        "repo": "langchain-ai/langchain",
        "github_url": "https://github.com/langchain-ai/langchain",
    },
    "chromadb": {
        "import_names": ["chromadb"],
        "repo": "chroma-core/chroma",
        "github_url": "https://github.com/chroma-core/chroma",
    },
    "sqlalchemy": {
        "import_names": ["sqlalchemy"],
        "repo": "sqlalchemy/sqlalchemy",
        "github_url": "https://github.com/sqlalchemy/sqlalchemy",
    },
    "requests": {
        "import_names": ["requests"],
        "repo": "psf/requests",
        "github_url": "https://github.com/psf/requests",
    },
    "httpx": {
        "import_names": ["httpx"],
        "repo": "encode/httpx",
        "github_url": "https://github.com/encode/httpx",
    },
    "uvicorn": {
        "import_names": ["uvicorn"],
        "repo": "encode/uvicorn",
        "github_url": "https://github.com/encode/uvicorn",
    },
    "numpy": {
        "import_names": ["numpy", "np"],
        "repo": "numpy/numpy",
        "github_url": "https://github.com/numpy/numpy",
    },
    "pandas": {
        "import_names": ["pandas", "pd"],
        "repo": "pandas-dev/pandas",
        "github_url": "https://github.com/pandas-dev/pandas",
    },
    "openai": {
        "import_names": ["openai"],
        "repo": "openai/openai-python",
        "github_url": "https://github.com/openai/openai-python",
    },
    "sentence-transformers": {
        "import_names": ["sentence_transformers"],
        "repo": "UKPLab/sentence-transformers",
        "github_url": "https://github.com/UKPLab/sentence-transformers",
    },
    "pytest": {
        "import_names": ["pytest"],
        "repo": "pytest-dev/pytest",
        "github_url": "https://github.com/pytest-dev/pytest",
    },
    "pyyaml": {
        "import_names": ["yaml"],
        "repo": "yaml/pyyaml",
        "github_url": "https://github.com/yaml/pyyaml",
    },
    "pillow": {
        "import_names": ["PIL"],
        "repo": "python-pillow/Pillow",
        "github_url": "https://github.com/python-pillow/Pillow",
    },
    "scikit-learn": {
        "import_names": ["sklearn"],
        "repo": "scikit-learn/scikit-learn",
        "github_url": "https://github.com/scikit-learn/scikit-learn",
    },
}

GITHUB_URL_PATTERN = re.compile(r"https?://github\.com/([a-zA-Z0-9_\-\.]+)/([a-zA-Z0-9_\-\.]+)")

# In-memory lookup cache to avoid repeating remote PyPI queries
_RESOLVED_CACHE: Dict[str, Tuple[List[str], Optional[str]]] = {}

def normalize_package_name(name: str) -> str:
    return name.lower().replace("_", "-").strip()

def get_import_names_for_package(pkg_name: str) -> List[str]:
    """Returns the top-level Python import names associated with this PyPI package."""
    norm = normalize_package_name(pkg_name)
    if norm in KNOWN_PACKAGES:
        return KNOWN_PACKAGES[norm]["import_names"]
    # Standard Python packaging convention: hyphens become underscores
    standard_import = norm.replace("-", "_")
    return [standard_import]

def extract_github_repo_from_url(url: str) -> Optional[str]:
    """Extracts 'owner/repo' from a GitHub URL string."""
    if not url:
        return None
    match = GITHUB_URL_PATTERN.search(url)
    if match:
        owner = match.group(1)
        repo = match.group(2).rstrip(".git")
        return f"{owner}/{repo}"
    return None

def resolve_package_metadata(pkg_name: str) -> Tuple[List[str], Optional[str]]:
    """
    Returns (import_names, github_repo_slug).
    Uses known table first, then PyPI JSON API as fallback.
    """
    norm = normalize_package_name(pkg_name)
    if norm in _RESOLVED_CACHE:
        return _RESOLVED_CACHE[norm]

    if norm in KNOWN_PACKAGES:
        entry = KNOWN_PACKAGES[norm]
        result = (entry["import_names"], entry["repo"])
        _RESOLVED_CACHE[norm] = result
        return result

    import_names = [norm.replace("-", "_")]
    repo_slug: Optional[str] = None

    # Fallback to PyPI JSON API
    try:
        url = f"https://pypi.org/pypi/{norm}/json"
        with httpx.Client(timeout=4.0) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                info = data.get("info", {})
                project_urls = info.get("project_urls") or {}
                
                # Check project_urls dict
                candidates = list(project_urls.values())
                if info.get("home_page"):
                    candidates.append(info.get("home_page"))

                for candidate in candidates:
                    if candidate and isinstance(candidate, str):
                        slug = extract_github_repo_from_url(candidate)
                        if slug:
                            repo_slug = slug
                            break
    except Exception as e:
        logger.debug(f"PyPI API lookup skipped or failed for {norm}: {e}")

    result = (import_names, repo_slug)
    _RESOLVED_CACHE[norm] = result
    return result
