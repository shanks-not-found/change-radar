"""
Dependency Parser for StackSignal.

Parses requirements.txt and pyproject.toml (PEP 621 and Poetry).
Extracts normalized package names, specifiers, exact pinned versions,
and source file provenance using `packaging`.
"""

import re
import tomllib
from pathlib import Path
from typing import Dict, List, Optional, Set
from packaging.requirements import Requirement, InvalidRequirement
from packaging.specifiers import SpecifierSet

from app.schemas import DependencyInfo

# Regex to find an exact pinned version like ==1.2.3 or ===1.2.3
EXACT_PIN_RE = re.compile(r"^={2,3}\s*([0-9a-zA-Z\.\-_+]+)$")

def extract_pinned_version(specifier_str: Optional[str]) -> Optional[str]:
    """If the specifier contains an exact pin ==X.Y.Z, returns X.Y.Z."""
    if not specifier_str:
        return None
    try:
        spec_set = SpecifierSet(specifier_str)
        for spec in spec_set:
            if spec.operator in ("==", "==="):
                return spec.version
    except Exception:
        pass
    
    # Fallback regex
    for part in specifier_str.split(","):
        part = part.strip()
        match = EXACT_PIN_RE.match(part)
        if match:
            return match.group(1)
    return None

def parse_requirements_txt(
    file_path: Path,
    visited: Optional[Set[Path]] = None,
    base_dir: Optional[Path] = None,
) -> List[DependencyInfo]:
    """
    Parses a requirements.txt file, supporting:
    - Version specifiers (==, >=, <=, ~=, !=)
    - Extras (e.g. uvicorn[standard])
    - Comments (#)
    - Recursive includes (-r other.txt)
    - Environment markers (; sys_platform == 'win32')
    - Flags to ignore (-i, --index-url, -f, etc.)
    """
    if visited is None:
        visited = set()
    
    abs_path = file_path.resolve()
    if abs_path in visited or not abs_path.is_file():
        return []
    visited.add(abs_path)

    project_root = base_dir or abs_path.parent
    try:
        rel_source = str(abs_path.relative_to(project_root)).replace("\\", "/")
    except ValueError:
        rel_source = abs_path.name

    results: List[DependencyInfo] = []

    try:
        content = abs_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []

    lines = content.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1

        # Handle line continuation
        while line.endswith("\\") and i < len(lines):
            line = line[:-1].strip() + " " + lines[i].strip()
            i += 1

        # Strip comments
        if "#" in line:
            line = line.split("#", 1)[0].strip()

        if not line:
            continue

        # Handle recursive includes
        if line.startswith(("-r ", "--requirement ")):
            parts = line.split(maxsplit=1)
            if len(parts) == 2:
                include_target = (abs_path.parent / parts[1].strip()).resolve()
                results.extend(parse_requirements_txt(include_target, visited, project_root))
            continue

        # Skip CLI flags and URLs
        if line.startswith(("-i", "--index-url", "--extra-index-url", "-f", "--find-links", "--trusted-host")):
            continue

        # Parse requirement
        try:
            req = Requirement(line)
            pkg_name = req.name.lower().replace("_", "-")
            spec_str = str(req.specifier) if req.specifier else None
            pinned = extract_pinned_version(spec_str)

            results.append(
                DependencyInfo(
                    package_name=pkg_name,
                    specifier=spec_str or "*",
                    pinned_version=pinned,
                    source_file=rel_source,
                )
            )
        except InvalidRequirement:
            # Fallback heuristic for loose lines
            clean = re.split(r"[; \t]", line)[0].strip()
            match = re.match(r"^([a-zA-Z0-9_\-\.]+)(.*)$", clean)
            if match:
                pkg = match.group(1).lower().replace("_", "-")
                spec = match.group(2).strip() or None
                pinned = extract_pinned_version(spec)
                results.append(
                    DependencyInfo(
                        package_name=pkg,
                        specifier=spec or "*",
                        pinned_version=pinned,
                        source_file=rel_source,
                    )
                )

    return results

def parse_pyproject_toml(file_path: Path, base_dir: Optional[Path] = None) -> List[DependencyInfo]:
    """
    Parses pyproject.toml supporting:
    - PEP 621: [project.dependencies] and [project.optional-dependencies]
    - Poetry: [tool.poetry.dependencies]
    """
    abs_path = file_path.resolve()
    if not abs_path.is_file():
        return []

    project_root = base_dir or abs_path.parent
    try:
        rel_source = str(abs_path.relative_to(project_root)).replace("\\", "/")
    except ValueError:
        rel_source = abs_path.name

    results: List[DependencyInfo] = []

    try:
        content = abs_path.read_text(encoding="utf-8", errors="replace")
        data = tomllib.loads(content)
    except Exception:
        return []

    # 1. PEP 621 [project.dependencies]
    project_table = data.get("project", {})
    pep621_deps = project_table.get("dependencies", [])
    if isinstance(pep621_deps, list):
        for dep_str in pep621_deps:
            try:
                req = Requirement(dep_str)
                pkg = req.name.lower().replace("_", "-")
                spec = str(req.specifier) if req.specifier else None
                pinned = extract_pinned_version(spec)
                results.append(
                    DependencyInfo(
                        package_name=pkg,
                        specifier=spec or "*",
                        pinned_version=pinned,
                        source_file=rel_source,
                    )
                )
            except InvalidRequirement:
                continue

    # PEP 621 [project.optional-dependencies]
    opt_deps = project_table.get("optional-dependencies", {})
    if isinstance(opt_deps, dict):
        for group, group_deps in opt_deps.items():
            if isinstance(group_deps, list):
                for dep_str in group_deps:
                    try:
                        req = Requirement(dep_str)
                        pkg = req.name.lower().replace("_", "-")
                        spec = str(req.specifier) if req.specifier else None
                        pinned = extract_pinned_version(spec)
                        results.append(
                            DependencyInfo(
                                package_name=pkg,
                                specifier=spec or "*",
                                pinned_version=pinned,
                                source_file=f"{rel_source} [{group}]",
                            )
                        )
                    except InvalidRequirement:
                        continue

    # 2. Poetry [tool.poetry.dependencies]
    poetry_deps = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
    if isinstance(poetry_deps, dict):
        for pkg_raw, spec_raw in poetry_deps.items():
            if pkg_raw.lower() == "python":
                continue
            pkg = pkg_raw.lower().replace("_", "-")
            spec_str = None
            pinned = None

            if isinstance(spec_raw, str):
                spec_str = spec_raw
                # Poetry exact pin: "1.2.3" or "==1.2.3"
                if re.match(r"^[0-9]+(\.[0-9a-zA-Z]+)+$", spec_raw):
                    pinned = spec_raw
                    spec_str = f"=={spec_raw}"
                else:
                    pinned = extract_pinned_version(spec_raw)
            elif isinstance(spec_raw, dict):
                ver = spec_raw.get("version")
                if isinstance(ver, str):
                    spec_str = ver
                    if re.match(r"^[0-9]+(\.[0-9a-zA-Z]+)+$", ver):
                        pinned = ver
                        spec_str = f"=={ver}"
                    else:
                        pinned = extract_pinned_version(ver)

            results.append(
                DependencyInfo(
                    package_name=pkg,
                    specifier=spec_str or "*",
                    pinned_version=pinned,
                    source_file=rel_source,
                )
            )

    return results

def discover_and_parse_dependencies(project_dir: Path) -> List[DependencyInfo]:
    """
    Searches a project directory for requirements.txt and pyproject.toml,
    parses dependencies, and merges them uniquely by package name.
    """
    deps_by_pkg: Dict[str, DependencyInfo] = {}

    # Check root and subdirectories
    req_files = list(project_dir.glob("**/requirements*.txt"))
    pyproject_files = list(project_dir.glob("**/pyproject.toml"))

    # Skip ignored directories (.venv, venv, node_modules, .git)
    ignored = {".venv", "venv", "node_modules", ".git", "__pycache__", "build", "dist"}

    def is_valid(path: Path) -> bool:
        return not any(part in ignored for part in path.parts)

    for rf in filter(is_valid, req_files):
        parsed = parse_requirements_txt(rf, base_dir=project_dir)
        for dep in parsed:
            if dep.package_name not in deps_by_pkg or (not deps_by_pkg[dep.package_name].pinned_version and dep.pinned_version):
                deps_by_pkg[dep.package_name] = dep

    for pf in filter(is_valid, pyproject_files):
        parsed = parse_pyproject_toml(pf, base_dir=project_dir)
        for dep in parsed:
            if dep.package_name not in deps_by_pkg or (not deps_by_pkg[dep.package_name].pinned_version and dep.pinned_version):
                deps_by_pkg[dep.package_name] = dep

    return sorted(list(deps_by_pkg.values()), key=lambda d: d.package_name)
