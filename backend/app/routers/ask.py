"""
Ask Router for StackSignal.

Enables interactive grounded question-answering over a project's
dependencies, AST code references, and retrieved external evidence.
"""

from typing import List
from fastapi import APIRouter, HTTPException, status

from app.db import get_db
from app.schemas import AskRequest, AskResponse
from app.retrieval.hybrid import hybrid_search
from app.llm.llm_client import answer_question

router = APIRouter(prefix="/api", tags=["Ask Q&A"])

@router.post("/projects/{project_id}/ask", response_model=AskResponse)
def ask_project_question(project_id: str, payload: AskRequest) -> AskResponse:
    """Answers developer questions about dependency impact, grounded in project code and evidence passages."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM projects WHERE id = ?;", (project_id,))
        p = cursor.fetchone()
        if not p:
            raise HTTPException(status_code=404, detail="Project not found.")

        # Load dependencies and code references for context
        cursor.execute("SELECT package_name, pinned_version FROM dependencies WHERE project_id = ?;", (project_id,))
        deps = cursor.fetchall()

        cursor.execute("""
            SELECT package_name, file_path, line_number, snippet, symbol
            FROM code_references WHERE project_id = ? LIMIT 20;
        """, (project_id,))
        code_refs = cursor.fetchall()

    # Build project context summary
    dep_summary = ", ".join([f"{d['package_name']} (pinned: {d['pinned_version'] or 'none'})" for d in deps])
    code_lines = [
        f"- {r['package_name']} -> `{r['file_path']}:{r['line_number']}`: {r['snippet']}"
        for r in code_refs
    ]
    project_context = f"Project: {p['name']}\nDependencies: {dep_summary}\n\nKey Code References:\n" + "\n".join(code_lines)

    # Hybrid retrieve top evidence passages relevant to user question
    evidence_chunks = hybrid_search(
        query_text=payload.question,
        top_k=6,
    )

    # Call LLM client (Gemini or Mock depending on LLM_PROVIDER / API key)
    grounded = answer_question(
        question=payload.question,
        evidence=evidence_chunks,
        project_context=project_context,
    )

    return AskResponse(
        question=payload.question,
        answer=grounded.answer,
        cited_sources=grounded.cited_sources,
        confidence=grounded.confidence,
        caveats=grounded.caveats,
    )
