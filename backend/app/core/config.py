"""
Application configuration — loads environment variables via Pydantic BaseSettings.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """
    All configuration is loaded from environment variables (or .env file).
    """

    # ── Database ──────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/legal_rag"

    # ── Supabase ──────────────────────────────────────────────────────────
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_jwt_secret: str = ""

    # ── Milvus ────────────────────────────────────────────────────────────
    milvus_host: str = "localhost"
    milvus_port: str = "19530"
    milvus_collection: str = "fasl_trace_chunks"
    vector_dimension: int = 1024

    # ── Encryption ────────────────────────────────────────────────────────
    encryption_key: str = ""

    # ── Embedding ─────────────────────────────────────────────────────────
    embedding_model_name: str = "BAAI/bge-m3"
    embedding_batch_size: int = 32
    embedding_dimension: int = 1024

    # ── Chunking ──────────────────────────────────────────────────────────
    chunk_target_size: int = 768  # target tokens per chunk
    chunk_min_size: int = 512
    chunk_max_size: int = 1024
    chunk_overlap_ratio: float = 0.2  # 20% overlap for semantic fallback

    # ── App ───────────────────────────────────────────────────────────────
    app_name: str = "legal-rag"
    debug: bool = False
    openapi_url: str = "/openapi.json"

    model_config = {
        "env_file": "../.env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton — avoids re-reading .env on every request."""
    return Settings()
