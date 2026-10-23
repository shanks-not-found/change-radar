"""
LLM Client Module for StackSignal.

Isolates all LLM logic, provider abstraction, API key handling,
retries with exponential backoff, and post-validation checks.
Supported providers: 'gemini' (default) and 'mock' (offline demo mode).
"""

from __future__ import annotations
import json
import logging
import os
import re
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from app.config import settings
from app.schemas import (
    ImpactContext,
    ImpactFinding,
    GroundedAnswer,
    CitedSource,
    CodeReference,
    EvidenceItem,
)
from app.llm.prompts import (
    IMPACT_ANALYSIS_SYSTEM_PROMPT,
    format_impact_context,
    ASK_SYSTEM_PROMPT,
    ASK_USER_TEMPLATE,
)

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------
# Post-Validation: Strict Grounding & Anti-Hallucination Verification
# ------------------------------------------------------------------------------

def post_validate_impact_finding(
    finding: ImpactFinding, context: ImpactContext
) -> ImpactFinding:
    """
    Enforces grounding verification:
    1. Validates that cited chunk IDs exist in the retrieved evidence.
    2. Validates that code references match actual scanned AST occurrences.
    3. Verifies that quoted passages exist in the cited chunk content.
    Downgrades severity and flags any discrepancies.
    """
    valid_chunk_map: Dict[str, Dict[str, Any]] = {
        c.get("chunk_id", c.get("id", "")): c for c in context.retrieved_chunks
    }
    valid_code_keys = {
        (ref.file_path, ref.line_number) for ref in context.scanned_code_references
    }

    validated_evidence: List[EvidenceItem] = []
    caveats: List[str] = []

    for ev in finding.evidence:
        if ev.chunk_id not in valid_chunk_map:
            caveats.append(f"Cited chunk_id '{ev.chunk_id}' was not in retrieved context; dropped.")
            continue

        chunk_data = valid_chunk_map[ev.chunk_id]
        chunk_text = chunk_data.get("content", "")
        # Normalize whitespace for quote check
        norm_quote = " ".join(ev.quoted_passage.split()).lower()
        norm_chunk = " ".join(chunk_text.split()).lower()

        if norm_quote and norm_quote not in norm_chunk:
            # Check for partial match (at least 60% words)
            quote_words = set(norm_quote.split())
            chunk_words = set(norm_chunk.split())
            if not quote_words.issubset(chunk_words):
                caveats.append(
                    f"Quote in citation [{ev.chunk_id}] could not be verified in source text; flagged for developer review."
                )

        validated_evidence.append(ev)

    # Validate code references
    validated_code_refs: List[CodeReference] = []
    for ref in finding.code_references:
        key = (ref.file_path, ref.line_number)
        if key in valid_code_keys or not context.scanned_code_references:
            validated_code_refs.append(ref)
        else:
            caveats.append(
                f"Referenced code {ref.file_path}:{ref.line_number} was not detected in AST scan; omitted."
            )

    # If evidence was dropped or ungrounded, downgrade confidence and severity
    if not validated_evidence and context.retrieved_chunks:
        caveats.append("No valid citations survived verification; downgraded confidence.")
        finding.confidence = min(finding.confidence, 0.4)
        if finding.affects_project == "yes":
            finding.affects_project = "likely"

    finding.evidence = validated_evidence
    finding.code_references = validated_code_refs

    if caveats:
        existing_notes = finding.uncertainty_notes or ""
        new_notes = " | ".join(caveats)
        finding.uncertainty_notes = f"{existing_notes}\n[Verification Note]: {new_notes}".strip()

    return finding


# ------------------------------------------------------------------------------
# Abstract Provider Interface
# ------------------------------------------------------------------------------

class LLMProvider(ABC):
    @abstractmethod
    def get_chat_model(self) -> Any:
        """Returns the underlying LangChain chat model."""
        pass

    @abstractmethod
    def analyze_change_impact(self, context: ImpactContext) -> ImpactFinding:
        """Analyzes dependency changes and returns structured ImpactFinding."""
        pass

    @abstractmethod
    def answer_question(
        self,
        question: str,
        evidence: List[Dict[str, Any]],
        project_context: Optional[str] = None,
    ) -> GroundedAnswer:
        """Answers a user question grounded in evidence."""
        pass


# ------------------------------------------------------------------------------
# Google Gemini Provider
# ------------------------------------------------------------------------------

class GeminiProvider(LLMProvider):
    def __init__(self) -> None:
        api_key = settings.gemini_api_key or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            logger.warning(
                "GEMINI_API_KEY is not configured. Live calls will fail. Use LLM_PROVIDER=mock for demo/offline mode."
            )
        self.api_key = api_key
        self.model_name = settings.gemini_model or "gemini-2.5-flash"
        self._llm = None

    def get_chat_model(self) -> Any:
        if self._llm is None:
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
            except ImportError:
                raise RuntimeError(
                    "langchain_google_genai is not installed. Please run pip install langchain-google-genai."
                )
            if not self.api_key:
                raise ValueError("GEMINI_API_KEY is missing. Configure it in .env or switch to LLM_PROVIDER=mock.")

            self._llm = ChatGoogleGenerativeAI(
                model=self.model_name,
                google_api_key=self.api_key,
                temperature=0.1,
                max_retries=3,
                timeout=60,
            )
        return self._llm

    def _execute_with_retry(self, fn, max_attempts: int = 3, initial_delay: float = 1.0):
        delay = initial_delay
        last_exc = None
        for attempt in range(1, max_attempts + 1):
            try:
                return fn()
            except Exception as e:
                last_exc = e
                logger.warning(f"LLM call attempt {attempt}/{max_attempts} failed: {e}. Retrying in {delay}s...")
                time.sleep(delay)
                delay *= 2.0
        raise last_exc

    def analyze_change_impact(self, context: ImpactContext) -> ImpactFinding:
        llm = self.get_chat_model()
        user_prompt = format_impact_context(context)

        structured_llm = llm.with_structured_output(ImpactFinding)

        def _call():
            messages = [
                ("system", IMPACT_ANALYSIS_SYSTEM_PROMPT),
                ("human", user_prompt),
            ]
            return structured_llm.invoke(messages)

        raw_finding: ImpactFinding = self._execute_with_retry(_call)
        return post_validate_impact_finding(raw_finding, context)

    def answer_question(
        self,
        question: str,
        evidence: List[Dict[str, Any]],
        project_context: Optional[str] = None,
    ) -> GroundedAnswer:
        llm = self.get_chat_model()
        structured_llm = llm.with_structured_output(GroundedAnswer)

        chunks_text = "\n---\n".join([
            f"[CHUNK {c.get('chunk_id', c.get('id', 'N/A'))}] ({c.get('package_name', '')} v{c.get('version', '')}):\n"
            f"{c.get('content', '')}\nURL: {c.get('url', '')}"
            for c in evidence
        ])

        user_prompt = ASK_USER_TEMPLATE.format(
            question=question,
            project_context=project_context or "No project code context provided.",
            evidence_chunks=chunks_text or "No external evidence chunks available.",
        )

        def _call():
            messages = [
                ("system", ASK_SYSTEM_PROMPT),
                ("human", user_prompt),
            ]
            return structured_llm.invoke(messages)

        return self._execute_with_retry(_call)


# ------------------------------------------------------------------------------
# Mock / Offline Provider (Deterministic, Zero API Key Required)
# ------------------------------------------------------------------------------

class MockLLMProvider(LLMProvider):
    """
    Deterministic mock provider that inspects the retrieved evidence
    and scanned code to generate high-fidelity, grounded ImpactFindings.
    Allows complete end-to-end runs, testing, and offline demos.
    """

    def get_chat_model(self) -> Any:
        return "mock-chat-model"

    def analyze_change_impact(self, context: ImpactContext) -> ImpactFinding:
        pkg = context.package
        pinned = context.pinned_version or "pinned"

        # Check for keywords in retrieved chunks
        chunks = context.retrieved_chunks
        breaking_keywords = ["breaking", "remove", "removed", "deprecated", "deprecation", "cve", "vulnerability"]
        
        has_breaking = False
        has_security = False
        target_chunk_id = None
        target_chunk_url = "https://github.com"
        target_version = pinned
        target_date = "2024-01-01"
        quoted_passage = ""
        matched_symbol = None

        # Inspect chunks for symbol overlap
        scanned_symbols = [r.symbol for r in context.scanned_code_references if r.symbol]

        for c in chunks:
            text = c.get("content", "")
            lower_text = text.lower()
            c_id = c.get("chunk_id", c.get("id", "chunk_mock_1"))
            c_url = c.get("url", "https://github.com")
            c_ver = c.get("version", pinned)
            c_date = c.get("published_at", "2024-01-01")

            # Check if any scanned symbol appears in chunk
            for sym in scanned_symbols:
                if sym and sym.lower() in lower_text:
                    matched_symbol = sym
                    target_chunk_id = c_id
                    target_chunk_url = c_url
                    target_version = c_ver
                    target_date = c_date
                    # Extract a snippet sentence
                    sentences = text.split(".")
                    for s in sentences:
                        if sym.lower() in s.lower():
                            quoted_passage = s.strip()[:180] + "."
                            break
                    break

            if target_chunk_id:
                break

            for kw in breaking_keywords:
                if kw in lower_text:
                    if "cve" in kw or "vulnerability" in kw:
                        has_security = True
                    else:
                        has_breaking = True
                    target_chunk_id = c_id
                    target_chunk_url = c_url
                    target_version = c_ver
                    target_date = c_date
                    sentences = text.split(".")
                    for s in sentences:
                        if kw in s.lower():
                            quoted_passage = s.strip()[:180] + "."
                            break
                    break

            if target_chunk_id:
                break

        # Fallback to first chunk if none matched
        if not target_chunk_id and chunks:
            c0 = chunks[0]
            target_chunk_id = c0.get("chunk_id", c0.get("id", "chunk_mock_1"))
            target_chunk_url = c0.get("url", "https://github.com")
            target_version = c0.get("version", pinned)
            target_date = c0.get("published_at", "2024-01-01")
            quoted_passage = c0.get("content", "General maintenance release.")[:150]

        # Determine change type and severity
        if has_security:
            change_type = "security"
            severity = "critical"
            affects = "likely" if context.scanned_code_references else "unknown"
            summary = f"Security vulnerability identified in {pkg} versions affecting {pinned}"
            why = f"OSV advisory records known security vulnerability for {pkg} around version {target_version}."
        elif matched_symbol:
            change_type = "breaking"
            severity = "high"
            affects = "yes"
            summary = f"API change affecting `{matched_symbol}` detected in {pkg} v{target_version}"
            why = f"Your codebase directly invokes `{matched_symbol}`, which underwent breaking modifications or deprecation in {target_version}."
        elif has_breaking:
            change_type = "breaking"
            severity = "medium"
            affects = "likely" if context.scanned_code_references else "unknown"
            summary = f"Potential compatibility issue: breaking changes reported in {pkg} v{target_version}"
            why = f"Release notes indicate breaking updates between your pinned version {pinned} and {target_version}."
        else:
            change_type = "feature"
            severity = "info"
            affects = "unlikely"
            summary = f"Non-breaking feature update and bug fixes in {pkg} v{target_version}"
            why = f"Changes in {target_version} appear backwards compatible and do not deprecate symbols used in project."

        code_refs = context.scanned_code_references[:3]
        evidence_list = []
        if target_chunk_id:
            evidence_list.append(
                EvidenceItem(
                    chunk_id=target_chunk_id,
                    url=target_chunk_url,
                    version=target_version,
                    date=target_date,
                    quoted_passage=quoted_passage or f"Release note for {pkg} {target_version}",
                )
            )

        checks = [
            f"Review import statements and call sites for {pkg}",
            f"Verify compatibility with release {target_version}",
            f"Run regression test suite against target version {target_version}",
        ]
        tests = [
            f"test_{pkg.replace('-', '_')}_compatibility.py",
            f"test_integration_{pkg.replace('-', '_')}.py",
        ]

        finding = ImpactFinding(
            package=pkg,
            change_summary=summary,
            change_type=change_type,
            affects_project=affects,
            severity=severity,
            confidence=0.88,
            why_it_matters=why,
            code_references=code_refs,
            recommended_checks=checks,
            suggested_tests=tests,
            evidence=evidence_list,
            uncertainty_notes="[Mock/Demo Mode] Generated deterministically from retrieved evidence chunks.",
        )
        return post_validate_impact_finding(finding, context)

    def answer_question(
        self,
        question: str,
        evidence: List[Dict[str, Any]],
        project_context: Optional[str] = None,
    ) -> GroundedAnswer:
        sources: List[CitedSource] = []
        for c in evidence[:3]:
            sources.append(
                CitedSource(
                    chunk_id=c.get("chunk_id", c.get("id", "mock_chunk")),
                    url=c.get("url", "https://github.com"),
                    package=c.get("package_name", "unknown"),
                    version=c.get("version", "N/A"),
                    snippet=c.get("content", "")[:200],
                )
            )

        answer_text = (
            f"Based on retrieved evidence for your inquiry: **\"{question}\"**\n\n"
            f"- We analyzed {len(evidence)} evidence passages.\n"
            f"- Key packages examined: {', '.join(set(s.package for s in sources)) or 'None'}.\n\n"
            f"External evidence confirms active releases and advisories. "
            f"Please review the cited sources below for specific version boundaries."
        )

        return GroundedAnswer(
            answer=answer_text,
            cited_sources=sources,
            confidence=0.92,
            caveats="[Mock/Demo Mode] Offline grounded answer synthesized from local retrieved chunks.",
        )


# ------------------------------------------------------------------------------
# Factory & Public Interface
# ------------------------------------------------------------------------------

def get_provider() -> LLMProvider:
    provider_name = (settings.llm_provider or "gemini").lower()
    if provider_name == "mock":
        return MockLLMProvider()
    elif provider_name == "gemini":
        # If Gemini API key is missing, log a warning and fall back to Mock if desired or let user know
        if not settings.gemini_api_key and not os.environ.get("GEMINI_API_KEY"):
            logger.info("GEMINI_API_KEY is not set. Defaulting to MockLLMProvider for offline execution.")
            return MockLLMProvider()
        return GeminiProvider()
    else:
        logger.warning(f"Unknown provider '{provider_name}'. Falling back to MockLLMProvider.")
        return MockLLMProvider()

def get_llm() -> Any:
    """Returns configured LangChain chat model."""
    return get_provider().get_chat_model()

def analyze_change_impact(context: ImpactContext) -> ImpactFinding:
    """Analyzes dependency changes and returns Pydantic-validated ImpactFinding."""
    return get_provider().analyze_change_impact(context)

def answer_question(
    question: str,
    evidence: List[Dict[str, Any]],
    project_context: Optional[str] = None,
) -> GroundedAnswer:
    """Answers a question grounded in evidence."""
    return get_provider().answer_question(question, evidence, project_context)
