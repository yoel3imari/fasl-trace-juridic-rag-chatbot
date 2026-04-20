"""
Document Pydantic schemas for API requests and responses.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


# Response schemas
class DocumentBase(BaseModel):
    """Base document schema with common fields."""

    filename: str
    language: str
    status: str


class DocumentResponse(DocumentBase):
    """Document response schema returned by the API."""

    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime | None = None


class DocumentCreate(BaseModel):
    """Document creation request schema."""

    filename: str
    language: str = "en"


class DocumentListResponse(BaseModel):
    """Response for list of documents."""

    documents: list[DocumentResponse]
    total: int
