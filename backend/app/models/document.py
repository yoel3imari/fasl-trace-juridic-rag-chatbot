"""
Document model — tracks uploaded PDF documents and their ingestion status.
"""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class Document(BaseModel):
    """
    Represents an uploaded PDF document.

    Table: documents (plural snake_case per naming convention)
    """

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
