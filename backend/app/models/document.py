from sqlalchemy import Integer, String
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

    chunks = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


from app.models.chunk import DocumentChunk