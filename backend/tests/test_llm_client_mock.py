import pytest
from app.schemas import (
    ImpactContext,
    CodeReference,
    ImpactFinding,
    EvidenceItem,
)
from app.llm.llm_client import (
    MockLLMProvider,
    post_validate_impact_finding,
    analyze_change_impact,
    answer_question,
)

def test_mock_llm_provider_analyze():
    context = ImpactContext(
        package="langchain",
        pinned_version="0.1.10",
        scanned_code_references=[
            CodeReference(
                file_path="main.py",
                line_number=25,
                snippet="chain = LLMChain(llm=model, prompt=prompt)",
                symbol="LLMChain",
            )
        ],
        retrieved_chunks=[
            {
                "chunk_id": "chunk_lc_1",
                "package_name": "langchain",
                "version": "0.2.0",
                "url": "https://github.com/langchain-ai/langchain/releases",
                "published_at": "2024-05-15",
                "content": "Breaking change: Deprecated LLMChain class. Migrate to LangChain Expression Language (LCEL).",
            }
        ],
    )

    provider = MockLLMProvider()
    finding = provider.analyze_change_impact(context)

    assert isinstance(finding, ImpactFinding)
    assert finding.package == "langchain"
    assert finding.severity in ("critical", "high", "medium")
    assert finding.affects_project in ("yes", "likely")
    assert len(finding.evidence) == 1
    assert finding.evidence[0].chunk_id == "chunk_lc_1"
    assert len(finding.recommended_checks) > 0
    assert len(finding.suggested_tests) > 0

def test_post_validation_drops_hallucinated_chunk():
    context = ImpactContext(
        package="fastapi",
        pinned_version="0.100.0",
        scanned_code_references=[
            CodeReference(file_path="app.py", line_number=10, snippet="app = FastAPI()", symbol="FastAPI")
        ],
        retrieved_chunks=[
            {"chunk_id": "real_chunk_1", "content": "FastAPI update."}
        ],
    )

    finding = ImpactFinding(
        package="fastapi",
        change_summary="Fake breaking change",
        change_type="breaking",
        affects_project="yes",
        severity="high",
        confidence=0.9,
        why_it_matters="Matters",
        code_references=[
            CodeReference(file_path="app.py", line_number=10, snippet="app = FastAPI()", symbol="FastAPI"),
            CodeReference(file_path="nonexistent.py", line_number=999, snippet="bad()", symbol="bad"),
        ],
        evidence=[
            EvidenceItem(
                chunk_id="hallucinated_chunk_99",
                url="https://fake.url",
                version="1.0.0",
                quoted_passage="Not in context",
            )
        ],
    )

    validated = post_validate_impact_finding(finding, context)
    # The hallucinated chunk ID should have been dropped
    assert len(validated.evidence) == 0
    # The hallucinated code ref should have been omitted
    assert len(validated.code_references) == 1
    assert validated.code_references[0].file_path == "app.py"
    # Uncertainty notes should flag the discrepancy
    assert "Verification Note" in validated.uncertainty_notes

def test_answer_question():
    evidence = [
        {
            "chunk_id": "pyd_1",
            "package_name": "pydantic",
            "version": "2.0.0",
            "url": "https://github.com/pydantic/pydantic",
            "content": "Pydantic V2 replaced BaseModel.dict() with BaseModel.model_dump().",
        }
    ]
    resp = answer_question("Does Pydantic V2 remove dict()?", evidence, "Project uses dict()")
    assert resp.answer != ""
    assert len(resp.cited_sources) >= 1
    assert resp.confidence > 0.0
