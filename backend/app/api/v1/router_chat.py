"""
Chat router — SSE streaming chat endpoint with full RAG pipeline.
"""

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


# ── SSE helpers ──────────────────────────────────────────────────────────────


def _sse_event(data: dict) -> str:
    """Format a dict as an SSE ``data:`` message."""
    return "data: " + json.dumps(data) + "\n\n"


# ── Format helpers ───────────────────────────────────────────────────────────


def _format_context(chunks: list[dict]) -> str:
    """Format retrieved chunks into a system-prompt context block."""
    parts: list[str] = []
    for i, c in enumerate(chunks):
        source_num = i + 1
        meta = f"[Page {c.get('page_number', '?')}]"
        if c.get("section_title"):
            meta += f" — {c['section_title']}"
        parts.append(f"[Source {source_num}] {meta}\n{c.get('text', '')}")
    return "\n\n".join(parts)


def _format_sources(citations: list) -> str:
    """Format citations into a source list for the system prompt."""
    parts: list[str] = []
    for c in citations:
        meta = f"Page {c.page}"
        if c.section:
            meta += f", {c.section}"
        parts.append(f"[Source {c.source_index}] — {meta}")
    return "\n".join(parts)


# ── LLM streaming ────────────────────────────────────────────────────────────


async def _stream_llm(
    model_config: dict,
    system_prompt: str,
    user_query: str,
):
    """Yield token strings from the configured LLM provider.

    Routes by ``provider_type`` — supports ``openai``, ``anthropic``,
    and ``ollama``.  Raises on error; the caller is responsible for
    catching and yielding appropriate SSE error events.
    """
    import httpx

    provider_type = model_config["provider_type"]
    base_url = model_config["base_url"]
    api_key = model_config.get("api_key")
    model_name = model_config["model_name"]

    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    async with httpx.AsyncClient(timeout=120.0) as client:
        if provider_type == "openai":
            url = f"{base_url.rstrip('/')}/v1/chat/completions"
            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_query},
                ],
                "stream": True,
            }
            async with client.stream("POST", url, json=payload, headers=headers) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            delta = data.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue

        elif provider_type == "anthropic":
            url = f"{base_url.rstrip('/')}/v1/messages"
            payload = {
                "model": model_name,
                "messages": [{"role": "user", "content": user_query}],
                "system": system_prompt,
                "stream": True,
                "max_tokens": 4096,
            }
            anthropic_headers = {
                **headers,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
            async with client.stream("POST", url, json=payload, headers=anthropic_headers) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        if not data_str:
                            continue
                        try:
                            data = json.loads(data_str)
                            if data.get("type") == "content_block_delta":
                                delta = data.get("delta", {})
                                text = delta.get("text")
                                if text:
                                    yield text
                        except json.JSONDecodeError:
                            continue

        elif provider_type == "ollama":
            url = f"{base_url.rstrip('/')}/api/chat"
            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_query},
                ],
                "stream": True,
            }
            async with client.stream("POST", url, json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        msg = data.get("message", {})
                        content = msg.get("content")
                        if content:
                            yield content
                        if data.get("done"):
                            break
                    except json.JSONDecodeError:
                        continue

        else:
            raise ValueError(f"Unknown provider type: {provider_type}")


# ── Chat generator ───────────────────────────────────────────────────────────


async def _chat_stream_generator(
    resolved_query: str,
    resolved_collection_id: str | None,
    db: AsyncSession,
    current_user: dict,
):
    """Full RAG pipeline generator yielding SSE-formatted events."""
    # ── 1. Retrieval step ────────────────────────────────────────────────
    yield _sse_event({"type": "processing_step", "step": "retrieval", "status": "active"})

    # Lazy imports — avoid loading heavy dependencies (pymilvus, sentence
    # transformers, flashrank, …) at app startup.
    from app.services.retrieval_pipeline import retrieve
    from app.services.llm_service import resolve_active_model

    # ── 2. Build context via retrieval ───────────────────────────────────
    user_id_int = abs(hash(str(current_user["user_id"])))
    try:
        result = await retrieve(query=resolved_query, user_id=user_id_int, top_k=5)
    except Exception as e:
        yield _sse_event({"type": "error", "content": f"Retrieval failed: {str(e)[:200]}"})
        return

    yield _sse_event({"type": "processing_step", "step": "retrieval", "status": "complete"})

    # ── 3. Handle abstention ─────────────────────────────────────────────
    if result.abstained:
        yield _sse_event({
            "type": "error",
            "content": "I don't have sufficient information to answer this question "
                       "based on the available documents.",
        })
        return

    # ── 4. Build system prompt from retrieved chunks ─────────────────────
    system_prompt = (
        "You are a legal analysis assistant. Answer the user's question based "
        "ONLY on the provided document context.\n\n"
        f"Context:\n{_format_context(result.chunks)}\n\n"
        "Instructions:\n"
        "- For each factual claim, cite the source as [Source N].\n"
        "- If the context does not contain enough information, say so clearly.\n"
        "- List all cited sources at the end of your response.\n\n"
        f"Sources:\n{_format_sources(result.citations)}"
    )

    # ── 5. Resolve generation model ──────────────────────────────────────
    yield _sse_event({"type": "processing_step", "step": "generation", "status": "active"})

    model_config = await resolve_active_model(db, UUID(current_user["user_id"]), "generation")
    if not model_config:
        yield _sse_event({
            "type": "error",
            "content": "No generation model configured. Please set up a model in Settings.",
        })
        return

    # ── 6. Stream LLM tokens ─────────────────────────────────────────────
    try:
        async for token in _stream_llm(model_config, system_prompt, resolved_query):
            yield _sse_event({"type": "token", "content": token})
    except Exception as e:
        yield _sse_event({"type": "error", "content": f"LLM streaming error: {str(e)[:200]}"})
        return

    yield _sse_event({"type": "processing_step", "step": "generation", "status": "complete"})

    # ── 7. Stream citations ──────────────────────────────────────────────
    citations_data = [
        {
            "source_index": c.source_index,
            "page": c.page,
            "section": c.section,
            "text": c.text[:200],
        }
        for c in result.citations
    ]
    yield _sse_event({"type": "citation", "citations": citations_data})

    # ── 8. Coverage warning ──────────────────────────────────────────────
    if result.coverage_warning:
        yield _sse_event({
            "type": "warning",
            "content": "Some legal topics referenced in your query may not be fully "
                       "covered by the available documents.",
        })

    # ── 9. Done event ────────────────────────────────────────────────────
    yield _sse_event({"type": "done"})


# ── Endpoint ─────────────────────────────────────────────────────────────────


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
    Runs the full RAG pipeline: retrieve context → call LLM → stream tokens
    → return citations.
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
        _chat_stream_generator(resolved_query, resolved_collection_id, db, current_user),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
