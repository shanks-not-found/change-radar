"""
Report Service for StackSignal.

Provides report querying, finding inspection, evidence retrieval,
explainability extraction, and export functions (Markdown & JSON).
"""

import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from app.db import get_db
from app.schemas import (
    ScanReportResponse,
    FindingResponse,
    FindingEvidenceResponse,
    FindingExplainability,
    SeverityCounts,
    CodeReference,
    EvidenceItem,
)

logger = logging.getLogger(__name__)

def build_finding_response_from_row(row: Any) -> FindingResponse:
    """Helper to deserialize database finding row into FindingResponse model."""
    code_refs = [CodeReference(**r) for r in json.loads(row["code_references_json"])]
    evidence_items = [EvidenceItem(**e) for e in json.loads(row["evidence_json"])]
    rec_checks = json.loads(row["recommended_checks_json"])
    sug_tests = json.loads(row["suggested_tests_json"])
    explain = FindingExplainability(**json.loads(row["explainability_json"]))

    created = row["created_at"]
    if isinstance(created, str):
        try:
            created = datetime.fromisoformat(created)
        except Exception:
            created = datetime.now(timezone.utc)

    return FindingResponse(
        id=row["id"],
        scan_id=row["scan_id"],
        project_id=row["project_id"],
        created_at=created,
        package=row["package"],
        change_summary=row["change_summary"],
        change_type=row["change_type"],
        affects_project=row["affects_project"],
        severity=row["severity"],
        confidence=float(row["confidence"]),
        why_it_matters=row["why_it_matters"],
        code_references=code_refs,
        recommended_checks=rec_checks,
        suggested_tests=sug_tests,
        evidence=evidence_items,
        uncertainty_notes=row["uncertainty_notes"],
        explainability=explain,
    )

def get_scan_report(scan_id: str) -> Optional[ScanReportResponse]:
    """Retrieves full scan report including all findings and aggregate counts."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.*, p.name AS project_name
            FROM scans s
            JOIN projects p ON p.id = s.project_id
            WHERE s.id = ?;
        """, (scan_id,))
        scan_row = cursor.fetchone()
        if not scan_row:
            return None

        cursor.execute("""
            SELECT * FROM findings
            WHERE scan_id = ?
            ORDER BY
                CASE severity
                    WHEN 'critical' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'medium' THEN 3
                    WHEN 'low' THEN 4
                    ELSE 5
                END ASC,
                confidence DESC;
        """, (scan_id,))
        finding_rows = cursor.fetchall()

        findings: List[FindingResponse] = [
            build_finding_response_from_row(r) for r in finding_rows
        ]

        # Calculate counts
        sev_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        aff_counts = {"yes": 0, "likely": 0, "unlikely": 0, "unknown": 0}

        for f in findings:
            s = f.severity.lower()
            if s in sev_counts:
                sev_counts[s] += 1
            a = f.affects_project.lower()
            if a in aff_counts:
                aff_counts[a] += 1

        created = scan_row["started_at"]
        if isinstance(created, str):
            try:
                created = datetime.fromisoformat(created)
            except Exception:
                created = datetime.now(timezone.utc)

        return ScanReportResponse(
            scan_id=scan_row["id"],
            project_id=scan_row["project_id"],
            project_name=scan_row["project_name"],
            status=scan_row["status"],
            created_at=created,
            total_findings=len(findings),
            severity_counts=SeverityCounts(**sev_counts),
            affects_counts=aff_counts,
            findings=findings,
        )

def get_finding_evidence(finding_id: str) -> Optional[FindingEvidenceResponse]:
    """Retrieves evidence citations and source code references for a finding."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM findings WHERE id = ?;", (finding_id,))
        row = cursor.fetchone()
        if not row:
            return None

        code_refs = [CodeReference(**r) for r in json.loads(row["code_references_json"])]
        evidence_items = [EvidenceItem(**e) for e in json.loads(row["evidence_json"])]

        return FindingEvidenceResponse(
            finding_id=row["id"],
            package=row["package"],
            evidence_items=evidence_items,
            code_references=code_refs,
        )

def get_finding_explainability(finding_id: str) -> Optional[FindingExplainability]:
    """Retrieves retrieval scores, matched symbols, and reasoning trail for a finding."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT explainability_json FROM findings WHERE id = ?;", (finding_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return FindingExplainability(**json.loads(row["explainability_json"]))

def generate_markdown_report(report: ScanReportResponse) -> str:
    """Renders the scan report into GitHub-flavored Markdown."""
    lines = [
        f"# StackSignal Impact Analysis Report",
        f"**Project:** {report.project_name} | **Scan ID:** `{report.scan_id}`",
        f"**Generated:** {report.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
        "## Summary Overview",
        f"- **Total Impact Findings:** {report.total_findings}",
        f"- **Critical:** {report.severity_counts.critical} | **High:** {report.severity_counts.high} | **Medium:** {report.severity_counts.medium} | **Low:** {report.severity_counts.low} | **Info:** {report.severity_counts.info}",
        "",
        "| Package | Severity | Affects Code? | Change Type | Summary |",
        "| :--- | :--- | :--- | :--- | :--- |",
    ]

    for f in report.findings:
        lines.append(
            f"| **{f.package}** | `{f.severity.upper()}` | {f.affects_project} | {f.change_type} | {f.change_summary} |"
        )

    lines.append("")
    lines.append("## Detailed Findings")
    for idx, f in enumerate(report.findings, start=1):
        lines.extend([
            f"### {idx}. [{f.severity.upper()}] {f.package}: {f.change_summary}",
            f"**Affects Project:** {f.affects_project} (Confidence: {f.confidence * 100:.0f}%)",
            f"**Why it matters:** {f.why_it_matters}",
            "",
        ])

        if f.code_references:
            lines.append("**Matched Project Code Locations:**")
            for ref in f.code_references:
                lines.append(f"- `{ref.file_path}:{ref.line_number}`")
                lines.append(f"  ```python\n  {ref.snippet}\n  ```")
            lines.append("")

        if f.evidence:
            lines.append("**Retrieved External Evidence:**")
            for ev in f.evidence:
                lines.append(f"- [{ev.chunk_id}] Version {ev.version} ([Source Link]({ev.url}))")
                lines.append(f"  > \"{ev.quoted_passage}\"")
            lines.append("")

        if f.recommended_checks:
            lines.append("**Recommended Verification Checks:**")
            for chk in f.recommended_checks:
                lines.append(f"- [ ] {chk}")
            lines.append("")

        if f.suggested_tests:
            lines.append("**Suggested Regression Tests:**")
            for tst in f.suggested_tests:
                lines.append(f"- `{tst}`")
            lines.append("")

        if f.uncertainty_notes:
            lines.append(f"> *Caveats/Notes:* {f.uncertainty_notes}")
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)
