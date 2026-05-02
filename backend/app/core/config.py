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
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/precise_rag"

    # ── Supabase ──────────────────────────────────────────────────────────
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_jwt_secret: str = ""

    # ── Encryption ────────────────────────────────────────────────────────
    encryption_key: str = ""

    # ── App ───────────────────────────────────────────────────────────────
    app_name: str = "precise-rag"
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
