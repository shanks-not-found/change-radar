import pytest
from app.retrieval.hybrid import reciprocal_rank_fusion, build_dependency_query
from app.retrieval.reranker import (
    calculate_symbol_overlap,
    calculate_keyword_boost,
    calculate_version_proximity,
    rerank_chunks,
)

def test_reciprocal_rank_fusion():
    vector_results = [
        {"chunk_id": "c1", "vector_score": 0.95},
        {"chunk_id": "c2", "vector_score": 0.85},
        {"chunk_id": "c3", "vector_score": 0.75},
    ]
    keyword_results = [
        {"chunk_id": "c2", "keyword_score": 0.90},
        {"chunk_id": "c4", "keyword_score": 0.80},
        {"chunk_id": "c1", "keyword_score": 0.70},
    ]

    fused = reciprocal_rank_fusion(vector_results, keyword_results, k_constant=60)
    top_id = fused[0]["chunk_id"]

    # c2 was rank 2 in vector and rank 1 in keyword -> should have highest RRF score
    assert top_id == "c2"
    assert fused[0]["rrf_score"] > fused[1]["rrf_score"]
    assert "vector_score" in fused[0]
    assert "keyword_score" in fused[0]

def test_build_dependency_query():
    query = build_dependency_query("fastapi", "0.109.0", ["APIRoute", "FastAPI", "Depends"])
    assert "fastapi" in query
    assert "0.109.0" in query
    assert "breaking" in query
    assert "APIRoute" in query

def test_calculate_symbol_overlap():
    text = "Deprecated LLMChain in favor of prompt | llm LCEL syntax."
    score, matched = calculate_symbol_overlap(text, {"LLMChain", "ChromaDB", "BaseModel"})

    assert "LLMChain" in matched
    assert score > 0.0

def test_calculate_keyword_boost():
    text = "Critical security vulnerability: CVE-2024-1234 allows remote code execution. Breaking change in auth."
    boost = calculate_keyword_boost(text)
    assert boost >= 0.6

def test_calculate_version_proximity():
    # Newer patch release
    p_patch = calculate_version_proximity("0.109.1", "0.109.0")
    # Older release
    p_older = calculate_version_proximity("0.100.0", "0.109.0")

    assert p_patch > p_older

def test_rerank_chunks():
    chunks = [
        {
            "chunk_id": "c1",
            "content": "Minor documentation fix for README.",
            "version": "0.109.1",
            "rrf_score": 0.03,
        },
        {
            "chunk_id": "c2",
            "content": "Breaking change: Removed LLMChain. Use LCEL pipelines.",
            "version": "0.110.0",
            "rrf_score": 0.025,
        },
    ]
    reranked = rerank_chunks(
        chunks=chunks,
        scanned_symbols=["LLMChain"],
        pinned_version="0.109.0",
        top_k=2,
    )
    # c2 mentions exact symbol and breaking change
    assert reranked[0]["chunk_id"] == "c2"
    assert "explainability" in reranked[0]
    assert "LLMChain" in reranked[0]["explainability"]["matched_symbols"]
