from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

# Backend root directory
BACKEND_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(BACKEND_DIR.parent / ".env"), str(BACKEND_DIR / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM Settings
    llm_provider: str = Field(default="gemini", alias="LLM_PROVIDER")
    gemini_api_key: Optional[str] = Field(default=None, alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.5-flash", alias="GEMINI_MODEL")
    github_token: Optional[str] = Field(default=None, alias="GITHUB_TOKEN")

    # Embeddings & RAG
    embedding_model: str = Field(default="BAAI/bge-small-en-v1.5", alias="EMBEDDING_MODEL")
    enable_cross_encoder: bool = Field(default=False, alias="ENABLE_CROSS_ENCODER")

    # Database & Storage
    database_path: str = Field(
        default=str(BACKEND_DIR / "data" / "stacksignal.db"),
        alias="DATABASE_PATH"
    )
    chroma_persist_dir: str = Field(
        default=str(BACKEND_DIR / "data" / "chroma"),
        alias="CHROMA_PERSIST_DIR"
    )

    # Server & Limits
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    cors_origins: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    max_upload_size_bytes: int = 50 * 1024 * 1024  # 50 MB
    version_window_releases: int = 25  # Max releases to ingest per package

settings = Settings()

def get_effective_gemini_key() -> Optional[str]:
    """Dynamically reads the Gemini API key from settings, env, or disk .env files."""
    if settings.gemini_api_key:
        return settings.gemini_api_key
    import os
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ.get("GEMINI_API_KEY")
    for env_path in (BACKEND_DIR.parent / ".env", BACKEND_DIR / ".env"):
        if env_path.exists():
            try:
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line.startswith("GEMINI_API_KEY=") and not line.startswith("#"):
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if val:
                            return val
            except Exception:
                pass
    return None

def get_effective_llm_provider() -> str:
    """Returns 'gemini' if key is present or provider configured as gemini, else 'mock'."""
    key = get_effective_gemini_key()
    if key:
        return "gemini"
    p = (settings.llm_provider or "gemini").lower().strip()
    return p

# Ensure data directories exist
Path(settings.database_path).parent.mkdir(parents=True, exist_ok=True)
Path(settings.chroma_persist_dir).mkdir(parents=True, exist_ok=True)
