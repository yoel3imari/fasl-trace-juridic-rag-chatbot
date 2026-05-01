"""
Document router - PDF upload and management endpoints.
"""

import asyncio
import logging
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
from app.services.pdf_engine import process_document


router = APIRouter(tags=["documents"])


UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "backend/uploads"))

MAX_FILENAME_LENGTH = 210
MIN_FILE_SIZE = 1024


def validate_pdf_magic_bytes(file: UploadFile) -> bool:
    original_pos = file.file.tell()
    file.file.seek(0)

    try:
        header = file.file.read(5)
        is_pdf = header == b"%PDF-"
    finally:
        file.file.seek(original_pos)

    return is_pdf


async def write_file_chunked(file: UploadFile, filepath: Path, chunk_size: int = 1024 * 1024):
    async with aiofiles.open(filepath, "wb") as f:
        while chunk := await file.read(chunk_size):
            await f.write(chunk)


logger = logging.getLogger(__name__)


async def _cleanup_file_async(file_path: Path):
    try:
        if file_path.exists():
            await run_in_threadpool(file_path.unlink)
    except Exception:
        logger.error("Failed to clean up file: %s", file_path, exc_info=True)


@router.post(
    "/documents/",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload PDF Document",
    description="Upload a PDF document for processing.",
)
async def upload_document(
    file: UploadFile = File(..., description="PDF file to upload (max 50MB)"),
    language: str = Form("en", description="Document language code: en, fr, ar"),
    db: AsyncSession = Depends(get_db_session_with_rls),
    current_user: dict = Depends(get_current_user),
):
    safe_name = file.filename if file.filename and file.filename.strip() else None
    if safe_name is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing filename in upload.",
        )

    if len(safe_name) > 255:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename too long.",
        )

    if not validate_pdf_magic_bytes(file):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type.",
        )

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
            detail="Empty file upload not allowed.",
        )

    max_size = 50 * 1024 * 1024
    if file_size > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds 50MB limit.",
        )

    stem = Path(safe_name).stem
    if len(stem) > MAX_FILENAME_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Filename stem too long.",
        )

    safe_filename = f"{stem}_{uuid4()}{Path(safe_name).suffix}"
    file_path = UPLOAD_DIR / safe_filename

    file_exists = True
    try:
        await write_file_chunked(file, file_path)
    except Exception:
        file_exists = False
        await _cleanup_file_async(file_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save file.",
        )

    try:
        user_id = UUID(current_user["user_id"])
    except (ValueError, TypeError):
        if file_exists:
            await _cleanup_file_async(file_path)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
        )

    valid_languages = {"en", "fr", "ar"}
    if language not in valid_languages:
        if file_exists:
            await _cleanup_file_async(file_path)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid language. Supported: {', '.join(sorted(valid_languages))}",
        )

    document = Document(
        filename=safe_filename,
        language=language,
        status="pending",
        user_id=user_id,
    )

    try:
        db.add(document)
        await db.commit()
        try:
            await db.refresh(document)
        except Exception:
            pass
        return document
    except Exception:
        await db.rollback()
        if file_exists:
            await _cleanup_file_async(file_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process upload.",
        )


@router.post(
    "/documents/{document_id}/process",
    summary="Process Document",
    description="Extract text and bounding boxes from PDF document.",
)
async def process_document_endpoint(
    document_id: UUID,
    db: AsyncSession = Depends(get_db_session_with_rls),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(Document)
        .where(Document.id == document_id)
        .where(Document.user_id == current_user["user_id"])
        .with_for_update()
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or access denied.",
        )

    if document.user_id != current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to process this document.",
        )

    if document.status not in ("pending", "failed"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Document status is '{document.status}', must be 'pending' or 'failed' to process.",
        )

    document.status = "processing"
    await db.commit()

    pdf_path = UPLOAD_DIR / document.filename
    if not pdf_path.exists():
        document.status = "failed"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file not available for processing.",
        )

    # NOTE: process_document is CPU-bound and blocks the event loop.
    # For production, consider making it sync and wrapping in run_in_threadpool.
    try:
        extraction = await process_document(pdf_path, document_id)
    except Exception:
        document.status = "failed"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PDF processing failed.",
        )

    if extraction.status == "failed":
        document.status = "failed"
        await db.commit()
        return {"status": "failed", "error": extraction.error}

    from app.models.chunk import DocumentChunk
    for chunk in extraction.chunks:
        db_chunk = DocumentChunk(
            document_id=document_id,
            chunk_index=chunk.block_index,
            page_number=chunk.page,
            text=chunk.text,
            bounding_box=chunk.bounding_box,
        )
        db.add(db_chunk)

    document.status = "processed"
    document.page_count = extraction.metadata.page_count
    document.detected_language = extraction.metadata.language
    await db.commit()

    return {
        "status": "processed",
        "metadata": {
            "page_count": extraction.metadata.page_count,
            "language": extraction.metadata.language,
            "chunk_count": len(extraction.chunks),
        },
    }


@router.get(
    "/documents/",
    response_model=DocumentListResponse,
    summary="List User Documents",
    description="Retrieve documents uploaded by the current user.",
)
async def list_documents(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session_with_rls),
):
    result = await db.execute(
        select(Document)
        .order_by(Document.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    documents = result.scalars().all()

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