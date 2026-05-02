from sqlalchemy import Integer, String, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Document(BaseModel):
    __tablename__ = "documents"

    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="ISO language code: en, fr, ar",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
        comment="pending | processing | processed | failed",
    )
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detected_language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    detected_languages: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="ISO 639-1 language codes detected in document (e.g. [\"ar\", \"en\"])",
    )
    error_log: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Structured error log for failed processing",
    )
    failed_blocks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Count of text blocks that failed extraction",
    )

    chunks = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


from app.models.chunk import DocumentChunk