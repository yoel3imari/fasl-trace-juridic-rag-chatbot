"""
Document router - PDF upload and management endpoints.
"""

import asyncio
import os
from pathlib import Path
from uuid import UUID, uuid4
from http import HTTPStatus
from io import BytesIO

import aiofiles
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db_session_with_rls
from app.core.security import get_current_user
from app.schemas.document import DocumentResponse, DocumentListResponse
from app.models.document import Document
from app.core.config import get_settings, Settings

# For RLS to work, we don't manually filter by user_id - PostgreSQL RLS
# uses auth.uid() which is set via SET LOCAL jwt.claims in get_db_session_with_rls

router = APIRouter(tags=["documents"])

# Configuration - directory creation happens at lifespan startup
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "backend/uploads"))

# Filesystem limits
MAX_FILENAME_LENGTH = 210  # Leaves room for UUID (36) + underscore
MIN_FILE_SIZE = 1024  # Minimum 1KB PDF (very small but valid)


def validate_pdf_magic_bytes(file: UploadFile) -> bool:
    """
    Validate that uploaded file is a PDF by checking magic bytes.

    PDF files always start with %PDF-1. (ASCII 0x25 0x50 0x44 0x46)
    This checks actual file content, not just the filename.

    Returns True if the first 5 bytes match the PDF signature.

    Note: Adobe's PDF spec allows up to 1024 bytes of garbage before %PDF-,
    but this strict validation is safer for security.
    """
    # Save current position and seek to start
    original_pos = file.file.tell()
    file.file.seek(0)

    try:
        # Read first 5 bytes (PDF signature: %PDF-)
        header = file.file.read(5)
        is_pdf = header == b"%PDF-"
    finally:
        # Restore original position
        file.file.seek(original_pos)

    return is_pdf


async def write_file_chunked(file: UploadFile, filepath: Path, chunk_size: int = 1024 * 1024):
    """
    Write an uploaded file to disk in chunks using async I/O.

    This prevents memory exhaustion by never loading the entire file into memory.
    Uses aiofiles for true async file I/O.
    """
    async with aiofiles.open(filepath, "wb") as f:
        while chunk := await file.read(chunk_size):
            await f.write(chunk)


def _cleanup_file_synchronous(file_path: Path):
    """
    Synchronous file cleanup helper.
    Called via run_in_threadpool to avoid blocking event loop.
    """
    try:
        if file_path.exists():
            file_path.unlink()
    except Exception:
        pass  # Log this in a real app


async def _cleanup_file_async(file_path: Path):
    """
    Async file cleanup helper using aiofiles.
    """
    try:
        if file_path.exists():
            await run_in_threadpool(file_path.unlink)
    except Exception:
        pass  # Log this in a real app


@router.post(
    "/documents/",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload PDF Document",
    description="Upload a PDF document for processing. Supports English, French, or Arabic.",
)
async def upload_document(
    file: UploadFile = File(..., description="PDF file to upload (max 50MB)"),
    language: str = Form("en", description="Document language code: en, fr, ar"),
    db: AsyncSession = Depends(get_db_session_with_rls),
    current_user: dict = Depends(get_current_user),
):
    """
    Upload a PDF document for processing.

    - **file**: PDF file (max 50MB) - validated by magic bytes
    - **language**: Language code (en, fr, ar), defaults to 'en'
    """
    # Edge Case 3: Handle None/empty filename in multipart header
    safe_name = file.filename if file.filename and file.filename.strip() else None
    if safe_name is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing filename in upload. Please provide a valid filename.",
        )

    # Edge Case 7: Filename path length validation
    if len(safe_name) > 255:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Filename too long. Maximum length is 255 characters. Received: {len(safe_name)}",
        )

    # Validate file is a PDF by checking magic bytes (not just extension)
    if not validate_pdf_magic_bytes(file):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. The uploaded file does not appear to be a PDF.",
        )

    # Edge Case 4: Zero-byte file validation
    original_pos = file.file.tell()
    try:
        file.file.seek(0, os.SEEK_END)
        file_size = file.file.tell()
        file.file.seek(original_pos)
    except Exception:
        file_size = 0

    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file upload not allowed. Please upload a valid PDF file.",
        )

    # Check file size (50MB limit)
    max_size = 50 * 1024 * 1024  # 50MB
    if file_size > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds 50MB limit. Current size: {file_size / (1024*1024):.2f}MB",
        )

    # Edge Case 7: Filename length with UUID (safe limit)
    stem = Path(safe_name).stem
    if len(stem) > MAX_FILENAME_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Filename too long. After removing extension, stem must be <= {MAX_FILENAME_LENGTH} characters.",
        )

    # Generate unique filename to avoid collisions
    safe_filename = f"{stem}_{uuid4()}{Path(safe_name).suffix}"
    file_path = UPLOAD_DIR / safe_filename

    # Track whether file exists for cleanup purposes
    file_exists = True
    try:
        # Edge Case 5: Stream file to disk in chunks using async I/O
        await write_file_chunked(file, file_path)
    except Exception:
        # File write failed - file may not exist or be incomplete
        file_exists = False
        # Clean up any partial write
        await _cleanup_file_async(file_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save file. Please try again later.",
        )

    # Validate user_id is a valid UUID format (Edge Case 8)
    try:
        user_id = UUID(current_user["user_id"])
    except (ValueError, TypeError):
        # File exists on disk but DB insert will fail - clean up
        if file_exists:
            await _cleanup_file_async(file_path)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
        )

    # Validate language parameter
    valid_languages = {"en", "fr", "ar"}
    if language not in valid_languages:
        if file_exists:
            await _cleanup_file_async(file_path)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid language. Supported: {', '.join(sorted(valid_languages))}",
        )

    # Create database record
    document = Document(
        filename=safe_name,
        language=language,
        status="pending",
        user_id=user_id,
    )

    try:
        db.add(document)
        await db.commit()
        # Edge Case 1: If refresh fails after commit, file should remain on disk
        # The transaction is already committed, so we cannot delete the file
        # without creating a "ghost" record
        try:
            await db.refresh(document)
        except Exception:
            # Refresh failed but commit succeeded - ghost record created
            # DO NOT delete the file as it would orphan the DB record
            pass
        return document
    except Exception:
        # Commit failed - no ghost record exists, safe to clean up
        if file_exists:
            await _cleanup_file_async(file_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process upload. Please try again later.",
        )


@router.get(
    "/documents/",
    response_model=DocumentListResponse,
    summary="List User Documents",
    description="Retrieve documents uploaded by the current user with pagination.",
)
async def list_documents(
    skip: int = Query(0, ge=0, description="Number of records to skip for pagination"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of records to return"),
    db: AsyncSession = Depends(get_db_session_with_rls),
):
    """
    List documents uploaded by the authenticated user.

    Supports pagination:
    - skip: Number of records to skip (default: 0)
    - limit: Maximum records to return (default: 20, max: 100)

    RLS is enforced at the database level via PostgreSQL Row-Level Security
    policies that use auth.uid() to verify the authenticated user.

    The application does NOT add manual WHERE user_id clauses - RLS handles
    tenant isolation automatically.
    """
    # Edge Case 2: Ensure we always have bounded pagination
    # Even though limit has default of 20 and max of 100, we add extra safety
    result = await db.execute(
        select(Document)
        .order_by(Document.created_at.desc())
        .offset(skip)
        .limit(limit)  # Always bounded by user input
    )
    documents = result.scalars().all()

    # Get total count for pagination metadata using SQL COUNT
    # Note: COUNT also respects RLS, so only user's documents are counted
    count_result = await db.execute(
        select(func.count(Document.id))
    )
    total = count_result.scalar_one()

    return {
        "documents": documents,
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get(
    "/documents/{document_id}/",
    response_model=DocumentResponse,
    summary="Get Document Details",
    description="Retrieve details of a specific document.",
)
async def get_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db_session_with_rls),
):
    """
    Get details of a specific document by ID.

    RLS is enforced at the database level via PostgreSQL Row-Level Security
    policies that use auth.uid() to verify the authenticated user.

    The application does NOT add manual WHERE user_id clauses - RLS handles
    tenant isolation automatically.
    """
    result = await db.execute(
        select(Document)
        .where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or access denied.",
        )

    return document
