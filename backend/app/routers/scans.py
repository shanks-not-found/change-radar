"""
Scans and Findings Router for StackSignal.

Handles:
- Scan execution trigger (background task)
- Real-time progress monitoring
- Report generation and filtering
- "Show me the evidence" drawer queries
- "Why was this flagged?" explainability queries
- Markdown and JSON report exports
- Scan history comparisons
"""

import json
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException, Response, status

from app.db import get_db
from app.schemas import (
    ScanCreateResponse,
    ScanStatusResponse,
    ScanReportResponse,
    FindingEvidenceResponse,
    FindingExplainability,
)
from app.services.scan_service import run_project_scan
from app.services.report_service import (
    get_scan_report,
    get_finding_evidence,
    get_finding_explainability,
    generate_markdown_report,
)

router = APIRouter(prefix="/api", tags=["Scans & Findings"])

@router.post("/projects/{project_id}/scans", response_model=ScanCreateResponse, status_code=status.HTTP_202_ACCEPTED)
def start_project_scan(
    project_id: str,
    background_tasks: BackgroundTasks,
) -> ScanCreateResponse:
    """Initiates an asynchronous multi-stage analysis scan for a project."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, local_path FROM projects WHERE id = ?;", (project_id,))
        p = cursor.fetchone()
        if not p:
            raise HTTPException(status_code=404, detail="Project not found.")

        scan_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        cursor.execute("""
            INSERT INTO scans (
                id, project_id, status, stage_description, progress_percentage, started_at
            ) VALUES (?, ?, ?, ?, ?, ?);
        """, (scan_id, project_id, "pending", "Initializing scan pipeline...", 0, now))

    # Queue execution in background tasks
    background_tasks.add_task(run_project_scan, scan_id, project_id, p["local_path"])

    return ScanCreateResponse(
        scan_id=scan_id,
        project_id=project_id,
        status="pending",
        message="Scan initiated in background. Poll /api/scans/{scan_id} for progress.",
    )


@router.get("/scans/{scan_id}", response_model=ScanStatusResponse)
def get_scan_status(scan_id: str) -> ScanStatusResponse:
    """Retrieves current stage, description, and completion percentage for an ongoing or finished scan."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM scans WHERE id = ?;", (scan_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Scan not found.")

    started = row["started_at"]
    if isinstance(started, str):
        try:
            started = datetime.fromisoformat(started)
        except Exception:
            started = datetime.now(timezone.utc)

    completed = None
    if row["completed_at"]:
        try:
            completed = datetime.fromisoformat(row["completed_at"])
        except Exception:
            completed = None

    return ScanStatusResponse(
        scan_id=row["id"],
        project_id=row["project_id"],
        status=row["status"],
        stage_description=row["stage_description"] or "Processing...",
        progress_percentage=row["progress_percentage"] or 0,
        error_message=row["error_message"],
        started_at=started,
        completed_at=completed,
    )


@router.get("/scans/{scan_id}/report", response_model=ScanReportResponse)
def get_report(scan_id: str) -> ScanReportResponse:
    """Retrieves the complete impact analysis report, ranked findings, and summary statistics."""
    report = get_scan_report(scan_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report or scan not found.")
    return report


@router.get("/findings/{finding_id}/evidence", response_model=FindingEvidenceResponse)
def get_evidence(finding_id: str) -> FindingEvidenceResponse:
    """Provides cited release note passages, source URLs, and matched code references for a finding."""
    evidence = get_finding_evidence(finding_id)
    if not evidence:
        raise HTTPException(status_code=404, detail="Finding evidence not found.")
    return evidence


@router.get("/findings/{finding_id}/explain", response_model=FindingExplainability)
def explain_finding(finding_id: str) -> FindingExplainability:
    """Returns retrieval scores (RRF/Vector/Keyword), matched API symbols, and LLM reasoning steps."""
    explain = get_finding_explainability(finding_id)
    if not explain:
        raise HTTPException(status_code=404, detail="Explainability details not found.")
    return explain


@router.get("/projects/{project_id}/scans", response_model=List[ScanStatusResponse])
def list_project_scans(project_id: str) -> List[ScanStatusResponse]:
    """Lists history of scans executed for a specific project."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM scans WHERE project_id = ? ORDER BY started_at DESC;", (project_id,))
        rows = cursor.fetchall()

    results: List[ScanStatusResponse] = []
    for row in rows:
        started = row["started_at"]
        if isinstance(started, str):
            try:
                started = datetime.fromisoformat(started)
            except Exception:
                started = datetime.now(timezone.utc)

        completed = None
        if row["completed_at"]:
            try:
                completed = datetime.fromisoformat(row["completed_at"])
            except Exception:
                completed = None

        results.append(
            ScanStatusResponse(
                scan_id=row["id"],
                project_id=row["project_id"],
                status=row["status"],
                stage_description=row["stage_description"] or "",
                progress_percentage=row["progress_percentage"] or 0,
                error_message=row["error_message"],
                started_at=started,
                completed_at=completed,
            )
        )
    return results


@router.get("/scans/{scan_id}/export/markdown")
def export_markdown(scan_id: str) -> Response:
    """Exports the full impact report as a formatted Markdown document."""
    report = get_scan_report(scan_id)
    if not report:
        raise HTTPException(status_code=404, detail="Scan report not found.")

    md_text = generate_markdown_report(report)
    return Response(
        content=md_text,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="stacksignal-report-{scan_id[:8]}.md"'}
    )


@router.get("/scans/{scan_id}/export/json")
def export_json(scan_id: str) -> Response:
    """Exports the full impact report as JSON."""
    report = get_scan_report(scan_id)
    if not report:
        raise HTTPException(status_code=404, detail="Scan report not found.")

    json_data = report.model_dump_json(indent=2)
    return Response(
        content=json_data,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="stacksignal-report-{scan_id[:8]}.json"'}
    )
