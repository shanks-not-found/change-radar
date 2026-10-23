import pytest
from pathlib import Path
from app.analysis.dependency_parser import (
    parse_requirements_txt,
    parse_pyproject_toml,
    discover_and_parse_dependencies,
    extract_pinned_version,
)

def test_extract_pinned_version():
    assert extract_pinned_version("==1.2.3") == "1.2.3"
    assert extract_pinned_version("===2.0.0") == "2.0.0"
    assert extract_pinned_version(">=1.0.0,<=2.0.0") is None
    assert extract_pinned_version("~=1.4.0") is None
    assert extract_pinned_version(None) is None

def test_parse_requirements_txt(tmp_path: Path):
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("""
# Core dependencies
fastapi==0.109.0
uvicorn[standard]>=0.27.0
pydantic==2.5.3 # pinned model library
requests~=2.31.0; sys_platform != 'win32'
--extra-index-url https://download.pytorch.org/whl/cpu
chromadb==0.4.22
""", encoding="utf-8")

    deps = parse_requirements_txt(req_file)
    dep_map = {d.package_name: d for d in deps}

    assert "fastapi" in dep_map
    assert dep_map["fastapi"].pinned_version == "0.109.0"

    assert "pydantic" in dep_map
    assert dep_map["pydantic"].pinned_version == "2.5.3"

    assert "uvicorn" in dep_map
    assert dep_map["uvicorn"].pinned_version is None

    assert "chromadb" in dep_map
    assert dep_map["chromadb"].pinned_version == "0.4.22"

def test_parse_requirements_recursive(tmp_path: Path):
    base_file = tmp_path / "requirements-base.txt"
    base_file.write_text("fastapi==0.109.0\n", encoding="utf-8")

    main_file = tmp_path / "requirements.txt"
    main_file.write_text("-r requirements-base.txt\nlangchain==0.1.10\n", encoding="utf-8")

    deps = parse_requirements_txt(main_file)
    dep_map = {d.package_name: d for d in deps}

    assert "fastapi" in dep_map
    assert "langchain" in dep_map
    assert dep_map["langchain"].pinned_version == "0.1.10"

def test_parse_pyproject_toml_pep621(tmp_path: Path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("""
[project]
name = "sample-app"
version = "0.1.0"
dependencies = [
    "fastapi>=0.100.0",
    "pydantic==2.6.1",
    "httpx",
]

[project.optional-dependencies]
test = [
    "pytest==8.1.1",
]
""", encoding="utf-8")

    deps = parse_pyproject_toml(pyproject)
    dep_map = {d.package_name: d for d in deps}

    assert "fastapi" in dep_map
    assert dep_map["pydantic"].pinned_version == "2.6.1"
    assert "httpx" in dep_map
    assert "pytest" in dep_map
    assert dep_map["pytest"].pinned_version == "8.1.1"

def test_parse_pyproject_toml_poetry(tmp_path: Path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("""
[tool.poetry.dependencies]
python = "^3.11"
requests = "2.31.0"
chromadb = { version = "==0.4.24" }
uvicorn = "^0.28.0"
""", encoding="utf-8")

    deps = parse_pyproject_toml(pyproject)
    dep_map = {d.package_name: d for d in deps}

    assert "requests" in dep_map
    assert dep_map["requests"].pinned_version == "2.31.0"
    assert dep_map["chromadb"].pinned_version == "0.4.24"
    assert "python" not in dep_map

def test_discover_and_parse_dependencies(tmp_path: Path):
    (tmp_path / "requirements.txt").write_text("fastapi==0.109.0\n", encoding="utf-8")
    sub = tmp_path / "backend"
    sub.mkdir()
    (sub / "requirements.txt").write_text("pydantic==2.5.3\n", encoding="utf-8")

    deps = discover_and_parse_dependencies(tmp_path)
    pkg_names = [d.package_name for d in deps]

    assert "fastapi" in pkg_names
    assert "pydantic" in pkg_names
