"""
Prompt templates and formatting for StackSignal LLM analysis and Q&A.
Strictly enforces evidence grounding and prevents hallucination of versions,
URLs, and code references.
"""

from typing import Any, Dict, List
from app.schemas import ImpactContext, CodeReference

IMPACT_ANALYSIS_SYSTEM_PROMPT = """You are StackSignal, an expert static analysis and software change impact reasoning system.
Your mission is to analyze external evidence (GitHub release notes, OSV vulnerability advisories) for a specific Python package dependency and determine how those changes impact the user's actual codebase.

CRITICAL GROUNDING AND ACCURACY RULES:
1. USE ONLY THE PROVIDED EVIDENCE. Do not invent, speculate, or draw from unmentioned release notes.
2. CITE VALID CHUNK IDs. Every claim must cite the exact `chunk_id` from the provided evidence. Never fabricate a chunk_id.
3. PREVENT HALLUCINATING CODE. You may only refer to code files, line numbers, and snippets explicitly listed under "SCANNED PROJECT CODE". Do not invent line numbers or files.
4. EXACT QUOTATIONS. For each cited evidence item, `quoted_passage` must be an exact or near-exact quote found directly in the evidence text.
5. CONSERVATIVE LANGUAGE:
   - Unless the evidence explicitly declares that an API used in the project was removed or changed in a breaking way, use cautious phrasing such as "potential compatibility issue" or "may require inspection".
   - If evidence is ambiguous, partial, or does not directly mention the symbols used in the user's project, set `affects_project` to "unknown" or "unlikely", and state the ambiguity in `uncertainty_notes`.
6. DO NOT FABRICATE URLs OR VERSIONS. Use only the exact URLs and version strings provided in the evidence items.

Return your analysis as a structured JSON object strictly matching the required schema.
"""

IMPACT_ANALYSIS_USER_TEMPLATE = """Analyze the following external evidence for package: **{package}**
Current pinned version in project: **{pinned_version}** (specifier: {specifier})

---
### SCANNED PROJECT CODE (Where this package is actually used):
{code_references_text}

---
### RETRIEVED EXTERNAL EVIDENCE (Release Notes & Security Advisories):
{evidence_chunks_text}

---
INSTRUCTIONS:
- Determine if any breaking changes, deprecations, removals, security vulnerabilities, or behavior changes in the evidence affect the user's code.
- If the project does not call the changed APIs or the version does not affect the project, mark `affects_project` as 'unlikely' or 'unknown' with low severity.
- If an exact symbol used in the project is removed or broken in a version newer than pinned, mark `affects_project` as 'yes' or 'likely' and highlight the code reference.
- Provide actionable `recommended_checks` and `suggested_tests`.
"""

def format_impact_context(context: ImpactContext) -> str:
    """Format the code references and retrieved chunks for the LLM prompt."""
    if not context.scanned_code_references:
        code_text = "No direct code invocations were detected in project AST."
    else:
        lines = []
        for ref in context.scanned_code_references:
            sym = f" [symbol: {ref.symbol}]" if ref.symbol else ""
            lines.append(f"- File: `{ref.file_path}`, Line {ref.line_number}{sym}\n  Code: `{ref.snippet.strip()}`")
        code_text = "\n".join(lines)

    if not context.retrieved_chunks:
        chunks_text = "No external evidence chunks retrieved."
    else:
        chunk_lines = []
        for c in context.retrieved_chunks:
            c_id = c.get("chunk_id", c.get("id", "unknown"))
            pkg = c.get("package_name", context.package)
            ver = c.get("version", "N/A")
            url = c.get("url", "")
            date = c.get("published_at", "")
            heading = c.get("section_heading", "Release Note")
            body = c.get("content", "").strip()

            chunk_lines.append(
                f"[CHUNK ID: {c_id}]\n"
                f"Package: {pkg} | Version: {ver} | Date: {date} | URL: {url}\n"
                f"Section: {heading}\n"
                f"Content:\n{body}\n"
            )
        chunks_text = "\n---\n".join(chunk_lines)

    return IMPACT_ANALYSIS_USER_TEMPLATE.format(
        package=context.package,
        pinned_version=context.pinned_version or "unpinned",
        specifier=context.specifier or "any",
        code_references_text=code_text,
        evidence_chunks_text=chunks_text,
    )


ASK_SYSTEM_PROMPT = """You are StackSignal, an AI assistant specialized in analyzing dependency impact on Python codebases.
Answer the user's question accurately and concisely, strictly grounded in the provided project context and retrieved external evidence.

RULES:
1. Always cite specific source chunk IDs and URLs for factual claims about package versions and changes.
2. If the user asks about an API or package for which evidence is missing, clearly explain that evidence has not been found rather than guessing.
3. When referencing project code, state the exact file path and line number.
4. Output a JSON object with:
   - answer: string (markdown formatted)
   - cited_sources: list of {chunk_id, url, package, version, snippet}
   - confidence: float between 0.0 and 1.0
   - caveats: optional note on limitations
"""

ASK_USER_TEMPLATE = """User Question: {question}

---
### PROJECT DEPENDENCIES & CODE USAGE:
{project_context}

---
### RETRIEVED EVIDENCE CHUNKS:
{evidence_chunks}
"""
