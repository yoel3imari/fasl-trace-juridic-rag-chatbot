from sqlalchemy import String, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
import uuid

from app.models.base import BaseModel


class ModelAssignment(BaseModel):
    __tablename__ = "model_assignments"

    provider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("llm_providers.id", ondelete="RESTRICT"),
        nullable=False,
        comment="FK to llm_providers.id",
    )
    model_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Model name e.g. gpt-4o, claude-3-5-sonnet, llama3",
    )
    system_function: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="retrieval | generation | evaluation",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
        comment="Only one active assignment per (user_id, system_function)",
    )
    health_status: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="verified | unreachable | None (not yet checked)",
    )
    health_message: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Health-check result message or error detail",
    )
