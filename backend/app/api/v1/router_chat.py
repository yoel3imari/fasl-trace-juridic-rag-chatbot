"""
Chat router — SSE streaming chat endpoint.
"""

import asyncio
import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db_session_with_rls
from app.core.security import get_current_user
from app.models.collection import Collection
from app.schemas.chat import ChatStreamRequest


router = APIRouter(tags=["chat"])


async def _generate_mock_stream():
    """Generator that yields SSE-formatted mock chat events."""
    yield "data: " + json.dumps({"type": "processing_step", "step": "vector_search", "status": "complete"}) + "\n\n"
    await asyncio.sleep(0.1)

    tokens = ["This ", "is ", "a ", "mock ", "response."]
    for token in tokens:
        yield "data: " + json.dumps({"type": "token", "content": token}) + "\n\n"
        await asyncio.sleep(0.1)

    yield "data: " + json.dumps({"type": "processing_step", "step": "generation", "status": "complete"}) + "\n\n"
    await asyncio.sleep(0.1)

    yield "data: " + json.dumps({"type": "done"}) + "\n\n"


@router.get("/chat/stream")
@router.post("/chat/stream")
async def chat_stream(
    query: str | None = Query(None, min_length=1),
    collection_id: str | None = Query(None),
    body: ChatStreamRequest | None = None,
    db: AsyncSession = Depends(get_db_session_with_rls),
    current_user: dict = Depends(get_current_user),
):
    """
    SSE streaming chat endpoint.

    Accepts both GET (?query=...&collection_id=...) and POST (JSON body).
    Returns a Server-Sent Events stream with mock processing steps and tokens.
    """
    # Resolve parameters from query or body
    if body is not None:
        resolved_query = body.query
        resolved_collection_id = body.collection_id
    else:
        if query is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="query is required",
            )
        resolved_query = query
        resolved_collection_id = collection_id

    # If collection_id is provided, verify it exists and belongs to user
    if resolved_collection_id is not None:
        try:
            collection_uuid = UUID(resolved_collection_id)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid collection_id format",
            )

        result = await db.execute(
            select(Collection)
            .where(Collection.id == collection_uuid)
            .where(Collection.user_id == current_user["user_id"])
        )
        collection = result.scalar_one_or_none()

        if not collection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Collection not found or access denied.",
            )

    return StreamingResponse(
        _generate_mock_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
