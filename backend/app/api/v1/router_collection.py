from datetime import datetime
from uuid import UUID
from http import HTTPStatus
from typing import List

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.core.database import get_db_session_with_rls
from app.core.security import get_current_user
from app.models.collection import Collection
from app.models.document import Document


class CollectionBase(BaseModel):
    name: str


class CollectionResponse(CollectionBase):
    id: UUID
    user_id: UUID
    created_at: datetime


class CollectionCreate(BaseModel):
    name: str


class CollectionListResponse(BaseModel):
    collections: list[CollectionResponse]
    total: int


class CollectionDocumentResponse(BaseModel):
    id: UUID
    filename: str
    language: str
    status: str


class CollectionDocumentsResponse(BaseModel):
    documents: list[CollectionDocumentResponse]
    total: int


router = APIRouter(tags=["collections"])


@router.post(
    "/collections/",
    response_model=CollectionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Collection",
    description="Create a new document collection.",
)
async def create_collection(
    collection_data: CollectionCreate,
    db: AsyncSession = Depends(get_db_session_with_rls),
    current_user: dict = Depends(get_current_user),
):
    if not collection_data.name or not collection_data.name.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Collection name is required.",
        )

    if len(collection_data.name) > 255:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Collection name too long. Maximum is 255 characters.",
        )

    try:
        user_id = UUID(current_user["user_id"])
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
        )

    collection = Collection(name=collection_data.name.strip(), user_id=user_id)

    try:
        db.add(collection)
        await db.commit()
        await db.refresh(collection)
        return collection
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create collection. Please try again.",
        )


@router.get(
    "/collections/",
    response_model=CollectionListResponse,
    summary="List Collections",
    description="List collections owned by the current user.",
)
async def list_collections(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Max records to return"),
    search: str | None = Query(None, description="Search by collection name"),
    db: AsyncSession = Depends(get_db_session_with_rls),
    current_user: dict = Depends(get_current_user),
):
    filters = [Collection.user_id == current_user["user_id"]]
    if search:
        filters.append(Collection.name.ilike(f"%{search}%"))

    result = await db.execute(
        select(Collection)
        .where(*filters)
        .order_by(Collection.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    collections = result.scalars().all()

    count_result = await db.execute(
        select(func.count(Collection.id))
        .where(*filters)
    )
    total = count_result.scalar_one()

    return {
        "collections": collections,
        "total": total,
    }


@router.get(
    "/collections/{collection_id}/",
    response_model=CollectionResponse,
    summary="Get Collection",
    description="Get a specific collection by ID.",
)
async def get_collection(
    collection_id: UUID,
    db: AsyncSession = Depends(get_db_session_with_rls),
):
    result = await db.execute(
        select(Collection)
        .where(Collection.id == collection_id)
    )
    collection = result.scalar_one_or_none()

    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found or access denied.",
        )

    return collection


@router.delete(
    "/collections/{collection_id}/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Collection",
    description="Delete a collection.",
)
async def delete_collection(
    collection_id: UUID,
    db: AsyncSession = Depends(get_db_session_with_rls),
):
    result = await db.execute(
        select(Collection)
        .where(Collection.id == collection_id)
    )
    collection = result.scalar_one_or_none()

    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found or access denied.",
        )

    try:
        await db.delete(collection)
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete collection.",
        )


@router.post(
    "/collections/{collection_id}/documents/",
    response_model=CollectionDocumentsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add Documents to Collection",
    description="Add one or more documents to a collection.",
)
async def add_documents_to_collection(
    collection_id: UUID,
    document_ids: List[UUID],
    db: AsyncSession = Depends(get_db_session_with_rls),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(Collection)
        .where(Collection.id == collection_id)
    )
    collection = result.scalar_one_or_none()

    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found or access denied.",
        )

    if not document_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one document_id is required.",
        )

    doc_result = await db.execute(
        select(Document)
        .where(Document.id.in_(document_ids))
    )
    documents = doc_result.scalars().all()

    found_ids = {doc.id for doc in documents}
    requested_ids = set(document_ids)
    missing_ids = requested_ids - found_ids

    if missing_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documents not found: {missing_ids}",
        )

    try:
        for doc in documents:
            collection.documents.append(doc)

        await db.commit()
        await db.refresh(collection)

        return {
            "documents": [
                {
                    "id": doc.id,
                    "filename": doc.filename,
                    "language": doc.language,
                    "status": doc.status,
                }
                for doc in collection.documents
            ],
            "total": len(collection.documents),
        }
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add documents to collection.",
        )


@router.delete(
    "/collections/{collection_id}/documents/{document_id}/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove Document from Collection",
    description="Remove a document from a collection.",
)
async def remove_document_from_collection(
    collection_id: UUID,
    document_id: UUID,
    db: AsyncSession = Depends(get_db_session_with_rls),
):
    result = await db.execute(
        select(Collection)
        .options(selectinload(Collection.documents))
        .where(Collection.id == collection_id)
    )
    collection = result.scalar_one_or_none()

    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found or access denied.",
        )

    doc_to_remove = None
    for doc in collection.documents:
        if doc.id == document_id:
            doc_to_remove = doc
            break

    if not doc_to_remove:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found in collection.",
        )

    try:
        collection.documents.remove(doc_to_remove)
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove document from collection.",
        )


@router.get(
    "/collections/{collection_id}/documents/",
    response_model=CollectionDocumentsResponse,
    summary="List Documents in Collection",
    description="List all documents in a collection.",
)
async def list_documents_in_collection(
    collection_id: UUID,
    db: AsyncSession = Depends(get_db_session_with_rls),
):
    result = await db.execute(
        select(Collection)
        .options(selectinload(Collection.documents))
        .where(Collection.id == collection_id)
    )
    collection = result.scalar_one_or_none()

    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found or access denied.",
        )

    return {
        "documents": [
            {
                "id": doc.id,
                "filename": doc.filename,
                "language": doc.language,
                "status": doc.status,
            }
            for doc in collection.documents
        ],
        "total": len(collection.documents),
    }