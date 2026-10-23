"""
Projects Router for StackSignal.

Handles:
- ZIP file upload with security validation
- GitHub repository cloning/downloading
- Demo project instant loader
- Project metadata and dependency querying
"""

import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List
from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.config import settings, BACKEND_DIR
from app.db import get_db
from app.schemas import (
    ProjectResponse,
    ProjectDetailResponse,
    ProjectCreateGitHub,
    DependencyInfo,
)
from app.analysis.project_loader import load_from_zip, load_from_github
from app.analysis.dependency_parser import discover_and_parse_dependencies
from app.analysis.code_scanner import scan_project_code

router = APIRouter(prefix="/api", tags=["Projects"])

@router.post("/projects/upload", response_model=ProjectDetailResponse, status_code=status.HTTP_201_CREATED)
async def upload_project_zip(file: UploadFile = File(...)) -> ProjectDetailResponse:
    """Uploads a ZIP archive of a Python project, extracts it safely, and indexes dependencies."""
    if not file.filename.endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must be a .zip archive."
        )

    content = await file.read()
    try:
        project_id, name, extracted_path = load_from_zip(content, file.filename)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to process ZIP: {str(e)}"
        )

    now = datetime.now(timezone.utc)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO projects (id, name, source_type, source_ref, local_path, created_at)
            VALUES (?, ?, ?, ?, ?, ?);
        """, (project_id, name, "zip", file.filename, str(extracted_path), now.isoformat()))

    # Initial parse of dependencies and code references
    deps = discover_and_parse_dependencies(extracted_path)
    with get_db() as conn:
        cursor = conn.cursor()
        for d in deps:
            cursor.execute("""
                INSERT INTO dependencies (project_id, package_name, specifier, pinned_version, source_file)
                VALUES (?, ?, ?, ?, ?);
            """, (project_id, d.package_name, d.specifier, d.pinned_version, d.source_file))

    return ProjectDetailResponse(
        id=project_id,
        name=name,
        source_type="zip",
        source_ref=file.filename,
        created_at=now,
        dependencies_count=len(deps),
        scans_count=0,
        dependencies=deps,
        total_code_references=0,
        symbols_used=[],
    )


@router.post("/projects/from-github", response_model=ProjectDetailResponse, status_code=status.HTTP_201_CREATED)
def create_project_from_github(payload: ProjectCreateGitHub) -> ProjectDetailResponse:
    """Downloads a public GitHub repository zipball and initializes the project."""
    try:
        project_id, name, extracted_path = load_from_github(payload.repo_url)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to download repository from GitHub: {str(e)}"
        )

    display_name = payload.name or name
    now = datetime.now(timezone.utc)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO projects (id, name, source_type, source_ref, local_path, created_at)
            VALUES (?, ?, ?, ?, ?, ?);
        """, (project_id, display_name, "github", payload.repo_url, str(extracted_path), now.isoformat()))

    deps = discover_and_parse_dependencies(extracted_path)
    with get_db() as conn:
        cursor = conn.cursor()
        for d in deps:
            cursor.execute("""
                INSERT INTO dependencies (project_id, package_name, specifier, pinned_version, source_file)
                VALUES (?, ?, ?, ?, ?);
            """, (project_id, d.package_name, d.specifier, d.pinned_version, d.source_file))

    return ProjectDetailResponse(
        id=project_id,
        name=display_name,
        source_type="github",
        source_ref=payload.repo_url,
        created_at=now,
        dependencies_count=len(deps),
        scans_count=0,
        dependencies=deps,
        total_code_references=0,
        symbols_used=[],
    )


@router.post("/demo/load", response_model=ProjectDetailResponse, status_code=status.HTTP_201_CREATED)
def load_demo_project() -> ProjectDetailResponse:
    """Loads the pre-bundled sample project (FastAPI + LangChain + ChromaDB) for instant evaluation."""
    sample_src = BACKEND_DIR / "sample_projects" / "demo_fastapi_langchain"
    if not sample_src.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sample project template not found on server."
        )

    project_id = f"demo-{uuid.uuid4().hex[:8]}"
    name = "Demo: FastAPI + LangChain AI Service"
    target_dir = Path(settings.database_path).parent / "projects" / project_id
    target_dir.mkdir(parents=True, exist_ok=True)

    # Copy sample files
    shutil.copytree(sample_src, target_dir, dirs_exist_ok=True)

    now = datetime.now(timezone.utc)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO projects (id, name, source_type, source_ref, local_path, created_at)
            VALUES (?, ?, ?, ?, ?, ?);
        """, (project_id, name, "demo", "sample_projects/demo_fastapi_langchain", str(target_dir), now.isoformat()))

    # Parse dependencies
    deps = discover_and_parse_dependencies(target_dir)
    pkg_names = [d.package_name for d in deps]
    scanned_map = scan_project_code(target_dir, pkg_names)

    total_refs = 0
    all_symbols = set()

    with get_db() as conn:
        cursor = conn.cursor()
        for d in deps:
            refs = scanned_map.get(d.package_name, [])
            d.usage_count = len(refs)
            total_refs += len(refs)
            for r in refs:
                if r.symbol:
                    all_symbols.add(r.symbol)

            cursor.execute("""
                INSERT INTO dependencies (
                    project_id, package_name, specifier, pinned_version, source_file, usage_count
                ) VALUES (?, ?, ?, ?, ?, ?);
            """, (project_id, d.package_name, d.specifier, d.pinned_version, d.source_file, d.usage_count))

    return ProjectDetailResponse(
        id=project_id,
        name=name,
        source_type="demo",
        source_ref="sample_projects/demo_fastapi_langchain",
        created_at=now,
        dependencies_count=len(deps),
        scans_count=0,
        dependencies=deps,
        total_code_references=total_refs,
        symbols_used=sorted(list(all_symbols)),
    )


@router.get("/projects", response_model=List[ProjectResponse])
def list_projects() -> List[ProjectResponse]:
    """Lists all uploaded or created projects."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.*,
                (SELECT COUNT(*) FROM dependencies d WHERE d.project_id = p.id) AS dep_count,
                (SELECT COUNT(*) FROM scans s WHERE s.project_id = p.id) AS scan_count
            FROM projects p
            ORDER BY p.created_at DESC;
        """)
        rows = cursor.fetchall()

    results: List[ProjectResponse] = []
    for r in rows:
        created = r["created_at"]
        if isinstance(created, str):
            try:
                created = datetime.fromisoformat(created)
            except Exception:
                created = datetime.now(timezone.utc)

        results.append(
            ProjectResponse(
                id=r["id"],
                name=r["name"],
                source_type=r["source_type"],
                source_ref=r["source_ref"],
                created_at=created,
                dependencies_count=r["dep_count"],
                scans_count=r["scan_count"],
            )
        )
    return results


@router.get("/projects/{project_id}", response_model=ProjectDetailResponse)
def get_project_detail(project_id: str) -> ProjectDetailResponse:
    """Retrieves detailed project metadata, detected dependencies, and code usage counts."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM projects WHERE id = ?;", (project_id,))
        p = cursor.fetchone()
        if not p:
            raise HTTPException(status_code=404, detail="Project not found.")

        cursor.execute("SELECT * FROM dependencies WHERE project_id = ? ORDER BY package_name;", (project_id,))
        dep_rows = cursor.fetchall()

        cursor.execute("SELECT * FROM code_references WHERE project_id = ?;", (project_id,))
        ref_rows = cursor.fetchall()

        cursor.execute("SELECT COUNT(*) FROM scans WHERE project_id = ?;", (project_id,))
        scan_count = cursor.fetchone()[0]

    deps: List[DependencyInfo] = []
    for d in dep_rows:
        deps.append(
            DependencyInfo(
                id=d["id"],
                package_name=d["package_name"],
                specifier=d["specifier"],
                pinned_version=d["pinned_version"],
                source_file=d["source_file"],
                latest_version=d["latest_version"],
                vulnerability_count=d["vulnerability_count"],
                usage_count=d["usage_count"],
            )
        )

    symbols = set()
    for r in ref_rows:
        if r["symbol"]:
            symbols.add(r["symbol"])

    created = p["created_at"]
    if isinstance(created, str):
        try:
            created = datetime.fromisoformat(created)
        except Exception:
            created = datetime.now(timezone.utc)

    return ProjectDetailResponse(
        id=p["id"],
        name=p["name"],
        source_type=p["source_type"],
        source_ref=p["source_ref"],
        created_at=created,
        dependencies_count=len(deps),
        scans_count=scan_count,
        dependencies=deps,
        total_code_references=len(ref_rows),
        symbols_used=sorted(list(symbols)),
    )
