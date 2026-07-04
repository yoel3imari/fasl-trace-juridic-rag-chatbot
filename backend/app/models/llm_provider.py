from sqlalchemy import String, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class LLMProvider(BaseModel):
    __tablename__ = "llm_providers"

    provider_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="openai | anthropic | ollama",
    )
    base_url: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
        comment="None for Ollama (uses default localhost). For OpenAI/Anthropic, enterpris endpoint preferred.",
    )
    api_version: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="e.g. 'v1' for OpenAI",
    )
    encrypted_api_key: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="AES-256-GCM encrypted API key; never returned to client",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
        comment="Soft-delete flag; inactive providers are not used by RAG pipeline",
    )
