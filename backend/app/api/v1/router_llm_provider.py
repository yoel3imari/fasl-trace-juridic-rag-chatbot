from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
from uuid import UUID

from app.core.security import get_current_user
from app.models.llm_provider import LLMProvider
from app.models.model_assignment import ModelAssignment
from app.schemas.llm_provider import (
    APIKeySet,
    APIKeyResponse,
    LLMProviderCreate,
    LLMProviderUpdate,
    LLMProviderResponse,
    LLMProviderListResponse,
)
from app.core.database import get_db_session_with_rls
from app.services.crypto_service import encrypt_api_key, mask_api_key, decrypt_api_key

router = APIRouter(prefix="/llm-providers", tags=["LLM Providers"])


PUBLIC_ENDPOINTS = {
    "api.openai.com": "Use enterprise endpoint (zero-data-retention) instead",
    "api.anthropic.com": "Use enterprise endpoint instead",
}


def check_public_endpoint_warning(base_url: Optional[str]) -> Optional[str]:
    if not base_url:
        return None
    try:
        from urllib.parse import urlparse
        hostname = urlparse(base_url).hostname or ""
    except Exception:
        return None
    for public, msg in PUBLIC_ENDPOINTS.items():
        if hostname == public or hostname.endswith("." + public):
            return f"Warning: Public endpoint detected. {msg}"
    return None


def get_user_id_fromClaims(current_user: dict) -> UUID:
    """Parse and validate user_id from current_user claims."""
    try:
        return UUID(current_user["user_id"])
    except (KeyError, ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
        )


def build_response(provider: LLMProvider, base_url: Optional[str] = None) -> LLMProviderResponse:
    """Build response with warning and has_api_key computed."""
    response = LLMProviderResponse.model_validate(provider)
    response.warning = check_public_endpoint_warning(base_url or provider.base_url)
    response.has_api_key = provider.encrypted_api_key is not None
    return response


@router.post("/", response_model=LLMProviderResponse, status_code=status.HTTP_201_CREATED)
async def create_llm_provider(
    payload: LLMProviderCreate,
    db: AsyncSession = Depends(get_db_session_with_rls),
    current_user: dict = Depends(get_current_user),
):
    user_id = get_user_id_fromClaims(current_user)

    existing = await db.execute(
        select(LLMProvider).where(
            LLMProvider.user_id == user_id,
            LLMProvider.provider_type == payload.provider_type,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Provider with type '{payload.provider_type}' already exists for this user.",
        )

    provider = LLMProvider(
        user_id=user_id,
        provider_type=payload.provider_type,
        base_url=payload.base_url,
        api_version=payload.api_version,
    )
    db.add(provider)
    await db.commit()
    await db.refresh(provider)

    return build_response(provider, payload.base_url)


@router.get("/", response_model=LLMProviderListResponse)
async def list_llm_providers(
    db: AsyncSession = Depends(get_db_session_with_rls),
    current_user: dict = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    user_id = get_user_id_fromClaims(current_user)

    count_result = await db.execute(
        select(func.count(LLMProvider.id)).where(
            LLMProvider.user_id == user_id
        )
    )
    total = count_result.scalar_one()

    result = await db.execute(
        select(LLMProvider)
        .where(LLMProvider.user_id == user_id)
        .order_by(LLMProvider.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    providers = result.scalars().all()

    return LLMProviderListResponse(
        items=[build_response(p) for p in providers],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{provider_id}", response_model=LLMProviderResponse)
async def get_llm_provider(
    provider_id: UUID,
    db: AsyncSession = Depends(get_db_session_with_rls),
    current_user: dict = Depends(get_current_user),
):
    user_id = get_user_id_fromClaims(current_user)

    result = await db.execute(
        select(LLMProvider).where(
            LLMProvider.id == provider_id,
            LLMProvider.user_id == user_id,
        )
    )
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return build_response(provider)


@router.put("/{provider_id}", response_model=LLMProviderResponse)
async def update_llm_provider(
    provider_id: UUID,
    payload: LLMProviderUpdate,
    db: AsyncSession = Depends(get_db_session_with_rls),
    current_user: dict = Depends(get_current_user),
):
    user_id = get_user_id_fromClaims(current_user)

    result = await db.execute(
        select(LLMProvider).where(
            LLMProvider.id == provider_id,
            LLMProvider.user_id == user_id,
        )
    )
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    from app.schemas.llm_provider import _OMIT
    if payload.base_url is not _OMIT:
        provider.base_url = payload.base_url
    if payload.api_version is not _OMIT:
        provider.api_version = payload.api_version
    if payload.is_active is not _OMIT:
        provider.is_active = payload.is_active

    await db.commit()
    await db.refresh(provider)
    return build_response(provider)


@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_llm_provider(
    provider_id: UUID,
    db: AsyncSession = Depends(get_db_session_with_rls),
    current_user: dict = Depends(get_current_user),
):
    user_id = get_user_id_fromClaims(current_user)

    result = await db.execute(
        select(LLMProvider).where(
            LLMProvider.id == provider_id,
            LLMProvider.user_id == user_id,
        )
    )
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    # Enforce Story 2.1 AC 4: prevent deletion if active model assignments exist
    active_count = await db.execute(
        select(func.count(ModelAssignment.id)).where(
            ModelAssignment.provider_id == provider_id,
            ModelAssignment.is_active == True,
        )
    )
    if active_count.scalar_one() > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete provider with active model assignments. Deactivate or remove assignments first.",
        )

    await db.delete(provider)
    await db.commit()


# ── API Key Management ─────────────────────────────────────────────────────


@router.post("/{provider_id}/api-key", response_model=APIKeyResponse, status_code=status.HTTP_201_CREATED)
async def set_provider_api_key(
    provider_id: UUID,
    payload: APIKeySet,
    db: AsyncSession = Depends(get_db_session_with_rls),
    current_user: dict = Depends(get_current_user),
):
    user_id = get_user_id_fromClaims(current_user)

    result = await db.execute(
        select(LLMProvider).where(
            LLMProvider.id == provider_id,
            LLMProvider.user_id == user_id,
        )
    )
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    try:
        provider.encrypted_api_key = encrypt_api_key(payload.api_key)
    except (ValueError, TypeError, Exception):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to encrypt API key. Check ENCRYPTION_KEY configuration.",
        )
    await db.commit()
    await db.refresh(provider)

    return APIKeyResponse(
        has_api_key=True,
        masked_key=mask_api_key(payload.api_key),
        updated_at=provider.updated_at,
    )


@router.get("/{provider_id}/api-key", response_model=APIKeyResponse)
async def get_provider_api_key_status(
    provider_id: UUID,
    db: AsyncSession = Depends(get_db_session_with_rls),
    current_user: dict = Depends(get_current_user),
):
    user_id = get_user_id_fromClaims(current_user)

    result = await db.execute(
        select(LLMProvider).where(
            LLMProvider.id == provider_id,
            LLMProvider.user_id == user_id,
        )
    )
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    masked = None
    if provider.encrypted_api_key:
        try:
            masked = mask_api_key(decrypt_api_key(provider.encrypted_api_key))
        except Exception:
            # Corrupted encrypted_api_key — treat as if no key is set
            masked = None

    return APIKeyResponse(
        has_api_key=provider.encrypted_api_key is not None,
        masked_key=masked,
        updated_at=provider.updated_at if provider.encrypted_api_key else None,
    )


@router.delete("/{provider_id}/api-key", response_model=APIKeyResponse)
async def delete_provider_api_key(
    provider_id: UUID,
    db: AsyncSession = Depends(get_db_session_with_rls),
    current_user: dict = Depends(get_current_user),
):
    user_id = get_user_id_fromClaims(current_user)

    result = await db.execute(
        select(LLMProvider).where(
            LLMProvider.id == provider_id,
            LLMProvider.user_id == user_id,
        )
    )
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    provider.encrypted_api_key = None
    await db.commit()
    await db.refresh(provider)

    return APIKeyResponse(
        has_api_key=False,
        masked_key=None,
        updated_at=provider.updated_at,
    )
