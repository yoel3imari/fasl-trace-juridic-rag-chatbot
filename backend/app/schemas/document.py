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
    page_count: int | None = None
    detected_languages: list[str] | None = None
    created_at: datetime
    updated_at: datetime | None = None


class IngestionStatusResponse(BaseModel):
    """Enriched document status response for ingestion dashboard."""

    id: UUID
    filename: str
    submitted_language: str
    status: str
    page_count: int | None = None
    chunk_count: int = 0
    failed_blocks: int = 0
    error_log: dict | None = None
    detected_languages: list[str] | None = None
    created_at: datetime
    updated_at: datetime | None = None


class IngestionStatusListResponse(BaseModel):
    """Paginated list of document ingestion statuses."""

    documents: list[IngestionStatusResponse]
    total: int
    skip: int
    limit: int


class DocumentCreate(BaseModel):
    """Document creation request schema."""

    filename: str
    language: str = "en"


class DocumentListResponse(BaseModel):
    """Response for list of documents."""

    documents: list[DocumentResponse]
    total: int
