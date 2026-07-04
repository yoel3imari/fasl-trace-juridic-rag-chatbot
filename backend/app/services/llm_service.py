import httpx
from uuid import UUID
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.llm_provider import LLMProvider
from app.services.crypto_service import decrypt_api_key


async def get_provider_base_url(
    db: AsyncSession,
    user_id: UUID,
    provider_type: str,
) -> Optional[str]:
    """Resolve base URL for a provider type. Returns None if not configured.

    NFR-S1 compliance: The RAG pipeline must call this function
    and use the returned URL — NO hardcoded public API URLs allowed.
    """
    result = await db.execute(
        select(LLMProvider)
        .where(LLMProvider.user_id == user_id)
        .where(LLMProvider.provider_type == provider_type)
        .where(LLMProvider.is_active == True)
        .order_by(LLMProvider.created_at.desc())
    )
    provider = result.scalar_one_or_none()
    return provider.base_url if provider else None


async def get_provider_api_key(
    db: AsyncSession,
    user_id: UUID,
    provider_type: str,
) -> Optional[str]:
    """Resolve and DECRYPT API key for LLM invocation. Returns None if not configured.

    NFR-S2 compliance: Decryption happens ONLY here, server-side.
    The decrypted key is NEVER serialized in any API response.
    """
    result = await db.execute(
        select(LLMProvider)
        .where(LLMProvider.user_id == user_id)
        .where(LLMProvider.provider_type == provider_type)
        .where(LLMProvider.is_active == True)
        .order_by(LLMProvider.created_at.desc())
    )
    provider = result.scalar_one_or_none()
    if not provider or not provider.encrypted_api_key:
        return None
    try:
        return decrypt_api_key(provider.encrypted_api_key)
    except Exception:
        return None



async def health_check_model(
    provider_type: str,
    base_url: str,
    api_key: str | None,
    model_name: str,
    timeout: float = 10.0,
) -> tuple[bool, str]:
    """Ping provider endpoint. Returns (success: bool, message: str).

    Best-effort validation — failure does NOT block assignment creation.
    """
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            if provider_type == "openai":
                url = f"{base_url.rstrip('/')}/v1/models/{model_name}"
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    return True, "verified"
                return False, f"OpenAI returned {resp.status_code}: {resp.text[:200]}"

            elif provider_type == "anthropic":
                url = f"{base_url.rstrip('/')}/v1/messages"
                payload = {
                    "model": model_name,
                    "max_tokens": 1,
                    "messages": [{"role": "user", "content": "ping"}],
                }
                resp = await client.post(url, json=payload, headers={
                    **headers,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                })
                if resp.status_code in (200, 201):
                    return True, "verified"
                return False, f"Anthropic returned {resp.status_code}: {resp.text[:200]}"

            elif provider_type == "ollama":
                url = f"{base_url.rstrip('/')}/api/chat"
                payload = {
                    "model": model_name,
                    "messages": [{"role": "user", "content": "ping"}],
                    "stream": False,
                }
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    return True, "verified"
                return False, f"Ollama returned {resp.status_code}: {resp.text[:200]}"
            else:
                return False, f"Unknown provider type: {provider_type}"

    except httpx.TimeoutException:
        return False, f"Health-check timed out after {timeout}s"
    except httpx.ConnectError as e:
        return False, f"Cannot connect to {base_url}: {e}"
    except Exception as e:
        return False, f"Health-check failed: {str(e)[:200]}"


async def resolve_active_model(
    db: AsyncSession,
    user_id: UUID,
    system_function: str,
) -> Optional[dict]:
    """Return active model config {model_name, provider_type, base_url, api_key, provider_id} or None.

    NFR-S1/S2 compliant: resolves from DB only, decrypts key in memory.
    """
    from app.models.model_assignment import ModelAssignment

    result = await db.execute(
        select(ModelAssignment, LLMProvider)
        .join(LLMProvider, ModelAssignment.provider_id == LLMProvider.id)
        .where(
            ModelAssignment.user_id == user_id,
            ModelAssignment.system_function == system_function,
            ModelAssignment.is_active == True,
            LLMProvider.is_active == True,
        )
        .order_by(ModelAssignment.created_at.desc())
        .limit(1)
    )
    row = result.one_or_none()
    if not row:
        return None

    assignment, provider = row
    api_key = None
    if provider.encrypted_api_key:
        try:
            api_key = decrypt_api_key(provider.encrypted_api_key)
        except Exception:
            api_key = None

    return {
        "model_name": assignment.model_name,
        "provider_type": provider.provider_type,
        "base_url": provider.base_url,
        "api_key": api_key,
        "provider_id": str(provider.id),
    }


async def get_all_active_assignments(
    db: AsyncSession,
    user_id: UUID,
) -> dict[str, dict | None]:
    """Return {function: config} for retrieval, generation, evaluation. None if unassigned."""
    return {
        func: await resolve_active_model(db, user_id, func)
        for func in ["retrieval", "generation", "evaluation"]
    }
