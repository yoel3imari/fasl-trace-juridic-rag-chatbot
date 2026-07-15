"""
Document router - PDF upload and management endpoints.
"""

import asyncio
import logging
import os
import traceback
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4
from typing import Literal
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

from app.core.database import get_db_session_service, get_db_session_with_rls
from app.core.security import get_current_user, require_admin
from app.schemas.document import DocumentResponse, DocumentListResponse, IngestionStatusResponse, IngestionStatusListResponse
from app.models.document import Document
from app.models.chunk import DocumentChunk
from app.core.config import get_settings, Settings
from app.services.pdf_engine import process_document


router = APIRouter(tags=["documents"])


UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads"))

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
        await db.refresh(document)
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
    except Exception as e:
        document.status = "failed"
        document.failed_blocks = 0
        tb = traceback.format_exc()
        document.error_log = {
            "error_type": type(e).__name__,
            "message": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "traceback_summary": tb[:2000] + ("...[truncated]" if len(tb) > 2000 else ""),
        }
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PDF processing failed.",
        )

    if extraction.status == "failed":
        document.status = "failed"
        document.failed_blocks = extraction.failed_blocks
        document.error_log = {
            "error_type": "ExtractionFailed",
            "message": extraction.error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "traceback_summary": "",
        }
        await db.commit()
        return {"status": "failed", "error": extraction.error}

    try:
        for chunk in extraction.chunks:
            db_chunk = DocumentChunk(
                document_id=document_id,
                user_id=current_user["user_id"],
                chunk_index=chunk.block_index,
                page_number=chunk.page,
                text=chunk.text,
                bounding_box=chunk.bounding_box,
                text_direction=chunk.text_direction,
            )
            db.add(db_chunk)

        document.status = "processed"
        document.error_log = None
        document.page_count = extraction.metadata.page_count
        document.failed_blocks = extraction.failed_blocks
        document.detected_languages = extraction.metadata.detected_languages

        # Run vector pipeline (non-fatal if it fails — document is still "processed")
        try:
            from app.services.pipeline_service import run_vector_pipeline
            user_id_int = abs(hash(str(current_user["user_id"])))
            vector_status = await run_vector_pipeline(
                extraction=extraction,
                user_id_int=user_id_int,
                document_id=document.id,
                is_system=False,
            )
            document.status = vector_status
        except Exception as vec_err:
            logger.warning(
                "Vector pipeline failed for document %s: %s", document.id, vec_err,
            )
            document.error_log = {
                "error_type": "VectorizationFailed",
                "message": str(vec_err),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        await db.commit()
    except Exception as e:
        document.status = "failed"
        document.failed_blocks = extraction.failed_blocks
        document.error_log = {
            "error_type": type(e).__name__,
            "message": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "traceback_summary": "",
        }
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save extracted chunks.",
        )

    return {
        "status": "processed",
        "metadata": {
            "page_count": extraction.metadata.page_count,
            "language": extraction.metadata.language,
            "chunk_count": len(extraction.chunks),
            "failed_blocks": extraction.failed_blocks,
        },
    }


@router.post(
    "/admin/documents/",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload System Document (Admin)",
    description="Admin-only: ingest an official-corpus PDF into the shared "
    "p_system Milvus partition. These documents are queryable by every user.",
)
async def upload_system_document(
    file: UploadFile = File(..., description="Official PDF to add to the shared corpus (max 50MB)"),
    language: str = Form("en", description="Document language code: en, fr, ar"),
    db: AsyncSession = Depends(get_db_session_service),
    admin: dict = Depends(require_admin),
):
    safe_name = file.filename if file.filename and file.filename.strip() else None
    if safe_name is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing filename in upload.",
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
            detail="File size exceeds 50MB limit.",
        )

    valid_languages = {"en", "fr", "ar"}
    if language not in valid_languages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid language. Supported: {', '.join(sorted(valid_languages))}",
        )

    stem = Path(safe_name).stem
    if len(stem) > MAX_FILENAME_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename stem too long.",
        )

    safe_filename = f"sys_{stem}_{uuid4()}{Path(safe_name).suffix}"
    file_path = UPLOAD_DIR / safe_filename

    try:
        await write_file_chunked(file, file_path)
    except Exception:
        await _cleanup_file_async(file_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save file.",
        )

    document = Document(
        filename=safe_filename,
        language=language,
        status="pending",
        user_id=UUID(admin["user_id"]),
        is_system=True,
    )

    try:
        db.add(document)
        await db.commit()
        await db.refresh(document)
        return document
    except Exception:
        await db.rollback()
        await _cleanup_file_async(file_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process upload.",
        )


@router.post(
    "/admin/documents/{document_id}/process",
    summary="Process System Document (Admin)",
    description="Admin-only: extract text and vectorize an official-corpus document "
    "into the shared p_system Milvus partition.",
)
async def process_system_document_endpoint(
    document_id: UUID,
    db: AsyncSession = Depends(get_db_session_service),
    admin: dict = Depends(require_admin),
):
    result = await db.execute(
        select(Document)
        .where(Document.id == document_id)
        .where(Document.is_system.is_(True))
        .with_for_update()
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="System document not found.",
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

    try:
        extraction = await process_document(pdf_path, document_id)
    except Exception as e:
        document.status = "failed"
        tb = traceback.format_exc()
        document.error_log = {
            "error_type": type(e).__name__,
            "message": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "traceback_summary": tb[:2000] + ("...[truncated]" if len(tb) > 2000 else ""),
        }
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PDF processing failed.",
        )

    if extraction.status == "failed":
        document.status = "failed"
        document.failed_blocks = extraction.failed_blocks
        document.error_log = {
            "error_type": "ExtractionFailed",
            "message": extraction.error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "traceback_summary": "",
        }
        await db.commit()
        return {"status": "failed", "error": extraction.error}

    try:
        for chunk in extraction.chunks:
            db_chunk = DocumentChunk(
                document_id=document_id,
                user_id=admin["user_id"],
                chunk_index=chunk.block_index,
                page_number=chunk.page,
                text=chunk.text,
                bounding_box=chunk.bounding_box,
                text_direction=chunk.text_direction,
            )
            db.add(db_chunk)

        document.status = "processed"
        document.error_log = None
        document.page_count = extraction.metadata.page_count
        document.failed_blocks = extraction.failed_blocks
        document.detected_languages = extraction.metadata.detected_languages

        try:
            from app.services.pipeline_service import run_vector_pipeline
            vector_status = await run_vector_pipeline(
                extraction=extraction,
                user_id_int=None,
                document_id=document.id,
                is_system=True,
            )
            document.status = vector_status
        except Exception as vec_err:
            logger.warning(
                "System vector pipeline failed for document %s: %s", document.id, vec_err,
            )
            document.error_log = {
                "error_type": "VectorizationFailed",
                "message": str(vec_err),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        await db.commit()
    except Exception as e:
        document.status = "failed"
        document.failed_blocks = extraction.failed_blocks
        document.error_log = {
            "error_type": type(e).__name__,
            "message": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "traceback_summary": "",
        }
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save extracted chunks.",
        )

    return {
        "status": "processed",
        "metadata": {
            "page_count": extraction.metadata.page_count,
            "language": extraction.metadata.language,
            "chunk_count": len(extraction.chunks),
            "failed_blocks": extraction.failed_blocks,
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
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(Document)
        .where(Document.user_id == current_user["user_id"])
        .order_by(Document.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    documents = result.scalars().all()

    count_result = await db.execute(
        select(func.count(Document.id)).where(
            Document.user_id == current_user["user_id"]
        )
    )
    total = count_result.scalar_one()

    return {
        "documents": documents,
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get(
    "/documents/ingestion-status",
    response_model=IngestionStatusListResponse,
    summary="Document Ingestion Status",
    description="Retrieve ingestion status for all documents uploaded by the current user.",
)
async def get_ingestion_status(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status_filter: Literal["pending", "processing", "processed", "failed"] | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db_session_with_rls),
    current_user: dict = Depends(get_current_user),
):
    base_query = (
        select(Document, func.count(DocumentChunk.id).label("chunk_count"))
        .outerjoin(DocumentChunk)
        .where(Document.user_id == current_user["user_id"])
        .group_by(Document.id)
    )

    if status_filter:
        base_query = base_query.where(Document.status == status_filter)

    count_query = select(func.count(Document.id)).where(
        Document.user_id == current_user["user_id"]
    )
    if status_filter:
        count_query = count_query.where(Document.status == status_filter)

    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    result = await db.execute(
        base_query.order_by(Document.created_at.desc()).offset(skip).limit(limit)
    )
    rows = result.all()

    ingestion_statuses = []
    for doc, chunk_count in rows:
        ingestion_statuses.append(
            IngestionStatusResponse(
                id=doc.id,
                filename=doc.filename,
                submitted_language=doc.language,
                status=doc.status,
                page_count=doc.page_count,
                chunk_count=chunk_count or 0,
                failed_blocks=doc.failed_blocks,
                error_log=doc.error_log,
                detected_languages=doc.detected_languages,
                created_at=doc.created_at,
                updated_at=doc.updated_at,
            )
        )

    return {
        "documents": ingestion_statuses,
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
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(Document)
        .where(Document.id == document_id)
        .where(Document.user_id == current_user["user_id"])
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or access denied.",
        )
    return document


@router.delete(
    "/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Document",
    description="Delete a document, its chunks, the source file, and vector embeddings.",
)
async def delete_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db_session_with_rls),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(Document)
        .where(Document.id == document_id)
        .where(Document.user_id == current_user["user_id"])
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or access denied.",
        )

    try:
        from app.services.vector_store_service import delete_document_chunks

        user_id_int = abs(hash(str(current_user["user_id"])))
        doc_id_int = abs(hash(str(document_id))) & 0x7FFFFFFFFFFFFFFF
        delete_document_chunks(user_id_int, doc_id_int)
    except Exception as exc:
        logger.warning("Failed to delete vector chunks for document %s: %s", document_id, exc)

    pdf_path = UPLOAD_DIR / document.filename
    await _cleanup_file_async(pdf_path)

    await db.delete(document)
    await db.commit()
