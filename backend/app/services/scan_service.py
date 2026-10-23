"""
Scan Service for StackSignal.

Orchestrates the entire multi-stage analysis workflow:
1. Parsing: requirements.txt & pyproject.toml
2. Scanning: AST walk of project code for API symbols and line numbers
3. Fetching: GitHub release notes (version windowed) and OSV security advisories
4. Indexing: Markdown chunking into ChromaDB vectors and SQLite FTS5
5. Retrieving: Hybrid search (RRF) + multi-signal reranking
6. Analyzing: LLM grounded impact assessment with post-validation
7. Reporting: Summary generation and persistence
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.db import get_db
from app.schemas import (
    ImpactContext,
    CodeReference,
    ScanStage,
    FindingExplainability,
)
from app.analysis.dependency_parser import discover_and_parse_dependencies
from app.analysis.code_scanner import scan_project_code
from app.analysis.package_map import resolve_package_metadata
from app.ingestion.pipeline import run_ingestion_for_dependencies
from app.retrieval.chunker import chunk_document, index_chunks_in_db
from app.retrieval.vector_store import add_chunks_to_vector_store
from app.retrieval.hybrid import hybrid_search, build_dependency_query
from app.retrieval.reranker import rerank_chunks
from app.llm.llm_client import analyze_change_impact

logger = logging.getLogger(__name__)

def update_scan_progress(
    scan_id: str,
    status: ScanStage,
    stage_description: str,
    progress_percentage: int,
    error_message: Optional[str] = None,
    summary_counts: Optional[Dict[str, Any]] = None,
) -> None:
    """Updates the status and progress of a scan in SQLite."""
    with get_db() as conn:
        cursor = conn.cursor()
        completed_at = datetime.now(timezone.utc).isoformat() if status in ("completed", "failed") else None
        counts_json = json.dumps(summary_counts) if summary_counts else None

        cursor.execute("""
            UPDATE scans SET
                status = ?,
                stage_description = ?,
                progress_percentage = ?,
                error_message = ?,
                completed_at = COALESCE(?, completed_at),
                summary_counts_json = COALESCE(?, summary_counts_json)
            WHERE id = ?;
        """, (
            status,
            stage_description,
            progress_percentage,
            error_message,
            completed_at,
            counts_json,
            scan_id,
        ))

def run_project_scan(scan_id: str, project_id: str, project_path_str: str) -> None:
    """
    Synchronous worker executing the full scan pipeline.
    Typically invoked in a FastAPI BackgroundTask or thread pool.
    """
    project_path = Path(project_path_str)
    logger.info(f"Starting Scan [{scan_id}] for Project [{project_id}] at {project_path}")

    try:
        # ----------------------------------------------------------------------
        # STAGE 1: Dependency Parsing
        # ----------------------------------------------------------------------
        update_scan_progress(scan_id, "parsing", "Parsing requirements.txt and pyproject.toml...", 10)
        dependencies = discover_and_parse_dependencies(project_path)
        logger.info(f"Discovered {len(dependencies)} dependencies for project {project_id}.")

        # Store dependencies in DB
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM dependencies WHERE project_id = ?", (project_id,))
            for dep in dependencies:
                cursor.execute("""
                    INSERT INTO dependencies (
                        project_id, package_name, specifier, pinned_version, source_file
                    ) VALUES (?, ?, ?, ?, ?);
                """, (
                    project_id,
                    dep.package_name,
                    dep.specifier,
                    dep.pinned_version,
                    dep.source_file,
                ))

        if not dependencies:
            update_scan_progress(
                scan_id, "completed",
                "No dependencies found in requirements.txt or pyproject.toml.", 100,
                summary_counts={"total": 0, "critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
            )
            return

        # ----------------------------------------------------------------------
        # STAGE 2: Code Scanning (AST)
        # ----------------------------------------------------------------------
        update_scan_progress(scan_id, "scanning_code", "Scanning Python AST for invoked APIs and line references...", 25)
        pkg_names = [d.package_name for d in dependencies]
        scanned_code_map = scan_project_code(project_path, pkg_names)

        # Store code references in DB
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM code_references WHERE project_id = ?", (project_id,))
            for pkg, refs in scanned_code_map.items():
                for ref in refs:
                    cursor.execute("""
                        INSERT INTO code_references (
                            project_id, package_name, file_path, line_number, snippet, symbol
                        ) VALUES (?, ?, ?, ?, ?, ?);
                    """, (
                        project_id,
                        pkg,
                        ref.file_path,
                        ref.line_number,
                        ref.snippet,
                        ref.symbol,
                    ))

        # ----------------------------------------------------------------------
        # STAGE 3 & 4: Ingestion (Releases & OSV Advisories)
        # ----------------------------------------------------------------------
        update_scan_progress(scan_id, "fetching_releases", "Fetching GitHub release notes...", 40)
        ingestion_results = run_ingestion_for_dependencies(dependencies)

        update_scan_progress(scan_id, "fetching_advisories", "Querying OSV vulnerability database...", 55)

        # ----------------------------------------------------------------------
        # STAGE 5: Indexing Chunks (ChromaDB + FTS5)
        # ----------------------------------------------------------------------
        update_scan_progress(scan_id, "indexing", "Chunking release evidence and building hybrid vector/FTS index...", 70)
        all_chunks: List[Dict[str, Any]] = []
        for pkg, summary in ingestion_results.items():
            for doc in summary.get("documents", []):
                doc_chunks = chunk_document(doc)
                all_chunks.extend(doc_chunks)

        if all_chunks:
            index_chunks_in_db(all_chunks)
            try:
                add_chunks_to_vector_store(all_chunks)
            except Exception as e:
                logger.warning(f"Vector store indexing warning: {e}")

        # ----------------------------------------------------------------------
        # STAGE 6 & 7: Retrieval and LLM Impact Analysis
        # ----------------------------------------------------------------------
        update_scan_progress(scan_id, "analyzing", "Retrieving evidence passages and analyzing code impact...", 85)

        findings_to_save: List[Dict[str, Any]] = []
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        affects_counts = {"yes": 0, "likely": 0, "unlikely": 0, "unknown": 0}

        for dep in dependencies:
            pkg = dep.package_name
            pinned = dep.pinned_version
            code_refs = scanned_code_map.get(pkg, [])
            symbols = [r.symbol for r in code_refs if r.symbol]

            # Build query & run hybrid search
            query = build_dependency_query(pkg, pinned, symbols)
            retrieved_candidates = hybrid_search(
                query_text=query,
                package_name=pkg,
                pinned_version=pinned,
                top_k=8,
            )

            # Rerank
            top_evidence = rerank_chunks(
                chunks=retrieved_candidates,
                scanned_symbols=symbols,
                pinned_version=pinned,
                top_k=5,
            )

            if not top_evidence and not code_refs:
                continue

            # Prepare context for LLM
            impact_context = ImpactContext(
                package=pkg,
                specifier=dep.specifier,
                pinned_version=pinned,
                scanned_code_references=code_refs,
                retrieved_chunks=top_evidence,
            )

            # Call LLM client (with automatic fallback to mock if no API key)
            finding = analyze_change_impact(impact_context)

            # Build Explainability
            matched_syms = []
            for ev in top_evidence:
                matched_syms.extend(ev.get("explainability", {}).get("matched_symbols", []))
            matched_syms = list(set(matched_syms))

            retrieval_scores = {
                "top_rrf_score": top_evidence[0].get("rrf_score", 0.0) if top_evidence else 0.0,
                "top_vector_score": top_evidence[0].get("vector_score", 0.0) if top_evidence else 0.0,
                "top_keyword_score": top_evidence[0].get("keyword_score", 0.0) if top_evidence else 0.0,
            }

            reasoning_trail = [
                f"Scanned AST identified {len(code_refs)} code call sites for package '{pkg}'.",
                f"Hybrid retrieval fetched {len(retrieved_candidates)} passages; top {len(top_evidence)} reranked into context.",
                f"External evidence evaluated against pinned version '{pinned or 'unpinned'}'.",
                f"LLM produced severity '{finding.severity}' with confidence {finding.confidence:.2f}.",
            ]

            explain = FindingExplainability(
                retrieval_scores=retrieval_scores,
                matched_symbols=matched_syms,
                reasoning_trail=reasoning_trail,
                validation_status="verified",
            )

            finding_id = str(uuid.uuid4())
            findings_to_save.append({
                "id": finding_id,
                "scan_id": scan_id,
                "project_id": project_id,
                "package": finding.package,
                "change_summary": finding.change_summary,
                "change_type": finding.change_type,
                "affects_project": finding.affects_project,
                "severity": finding.severity,
                "confidence": finding.confidence,
                "why_it_matters": finding.why_it_matters,
                "code_references_json": json.dumps([r.model_dump() for r in finding.code_references]),
                "recommended_checks_json": json.dumps(finding.recommended_checks),
                "suggested_tests_json": json.dumps(finding.suggested_tests),
                "evidence_json": json.dumps([e.model_dump() for e in finding.evidence]),
                "uncertainty_notes": finding.uncertainty_notes,
                "explainability_json": json.dumps(explain.model_dump()),
            })

            # Tally counts
            sev = finding.severity.lower()
            if sev in severity_counts:
                severity_counts[sev] += 1
            aff = finding.affects_project.lower()
            if aff in affects_counts:
                affects_counts[aff] += 1

        # ----------------------------------------------------------------------
        # STAGE 8: Persist Findings and Finalize
        # ----------------------------------------------------------------------
        with get_db() as conn:
            cursor = conn.cursor()
            for f in findings_to_save:
                cursor.execute("""
                    INSERT INTO findings (
                        id, scan_id, project_id, package, change_summary, change_type,
                        affects_project, severity, confidence, why_it_matters,
                        code_references_json, recommended_checks_json, suggested_tests_json,
                        evidence_json, uncertainty_notes, explainability_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
                """, (
                    f["id"],
                    f["scan_id"],
                    f["project_id"],
                    f["package"],
                    f["change_summary"],
                    f["change_type"],
                    f["affects_project"],
                    f["severity"],
                    f["confidence"],
                    f["why_it_matters"],
                    f["code_references_json"],
                    f["recommended_checks_json"],
                    f["suggested_tests_json"],
                    f["evidence_json"],
                    f["uncertainty_notes"],
                    f["explainability_json"],
                ))

        summary_data = {
            "total_findings": len(findings_to_save),
            "severity_counts": severity_counts,
            "affects_counts": affects_counts,
        }

        update_scan_progress(
            scan_id, "completed",
            f"Scan completed successfully with {len(findings_to_save)} impact findings.",
            100,
            summary_counts=summary_data,
        )
        logger.info(f"Scan [{scan_id}] successfully completed.")

    except Exception as e:
        logger.exception(f"Scan [{scan_id}] encountered fatal error: {e}")
        update_scan_progress(
            scan_id, "failed",
            f"Scan failed: {str(e)}", 100,
            error_message=str(e),
        )
