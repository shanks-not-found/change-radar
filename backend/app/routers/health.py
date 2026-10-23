"""
Health Router for StackSignal.

Checks and reports system readiness:
- Database connectivity
- ChromaDB vector store readiness
- Embedding model availability
- LLM provider status (live Gemini vs mock mode)
"""

import os
from fastapi import APIRouter
from app.config import settings
from app.db import get_db
from app.schemas import HealthResponse

router = APIRouter(prefix="/api/health", tags=["Health"])

@router.get("", response_model=HealthResponse)
def health_check() -> HealthResponse:
    # 1. Check DB
    db_ok = False
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1;")
            db_ok = bool(cursor.fetchone())
    except Exception:
        db_ok = False

    # 2. Check ChromaDB
    chroma_ok = False
    try:
        from app.retrieval.vector_store import get_chroma_collection
        col = get_chroma_collection()
        chroma_ok = col is not None
    except Exception:
        chroma_ok = False

    # 3. Check Embeddings
    embedding_loaded = False
    try:
        from app.retrieval.embeddings import get_embedding_model
        model = get_embedding_model()
        embedding_loaded = model is not None
    except Exception:
        embedding_loaded = False

    # 4. Check LLM Provider
    provider = settings.llm_provider.lower()
    has_gemini_key = bool(settings.gemini_api_key or os.environ.get("GEMINI_API_KEY"))
    llm_configured = True if provider == "mock" else has_gemini_key

    return HealthResponse(
        status="ok" if db_ok else "degraded",
        llm_provider=provider,
        llm_configured=llm_configured,
        gemini_model=settings.gemini_model,
        embedding_model=settings.embedding_model,
        embedding_loaded=embedding_loaded,
        database_ok=db_ok,
        chroma_ok=chroma_ok,
    )
