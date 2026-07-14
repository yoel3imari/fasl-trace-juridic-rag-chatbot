import logging
import time

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
from uuid import UUID

from app.core.security import get_current_user
from app.models.model_assignment import ModelAssignment
from app.models.llm_provider import LLMProvider
from app.schemas.model_assignment import (
    ModelAssignmentCreate,
    ModelAssignmentUpdate,
    ModelAssignmentResponse,
    ModelAssignmentListResponse,
)
from app.core.database import get_db_session_with_rls
from app.services.llm_service import health_check_model, get_provider_api_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/model-assignments", tags=["Model Assignments"])


def get_user_id_fromClaims(current_user: dict) -> UUID:
    """Parse and validate user_id from current_user claims."""
    try:
        return UUID(current_user["user_id"])
    except (KeyError, ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
        )


@router.post(
    "/", response_model=ModelAssignmentResponse, status_code=status.HTTP_201_CREATED
)
async def create_model_assignment(
    payload: ModelAssignmentCreate,
    db: AsyncSession = Depends(get_db_session_with_rls),
    current_user: dict = Depends(get_current_user),
):
    user_id = get_user_id_fromClaims(current_user)

    # Validate provider exists and belongs to user
    provider_result = await db.execute(
        select(LLMProvider).where(
            LLMProvider.id == payload.provider_id,
            LLMProvider.user_id == user_id,
        )
    )
    provider = provider_result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    # Validate provider is active
    if not provider.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot assign to an inactive provider.",
        )

    # Deactivate all existing active assignments for this (user_id, system_function)
    existing = await db.execute(
        select(ModelAssignment).where(
            ModelAssignment.user_id == user_id,
            ModelAssignment.system_function == payload.system_function,
            ModelAssignment.is_active == True,
        )
    )
    for assignment in existing.scalars().all():
        assignment.is_active = False
    await db.flush()

    # Perform health-check ping
    api_key = None
    if provider.encrypted_api_key:
        try:
            api_key = await get_provider_api_key(db, user_id, provider.provider_type)
        except Exception:
            api_key = None
    success, message = await health_check_model(
        provider_type=provider.provider_type,
        base_url=provider.base_url or "",
        api_key=api_key,
        model_name=payload.model_name,
    )

    health_status = "verified" if success else "unreachable"
    health_message = message

    assignment = ModelAssignment(
        user_id=user_id,
        provider_id=payload.provider_id,
        model_name=payload.model_name,
        system_function=payload.system_function,
        is_active=True,
        health_status=health_status,
        health_message=health_message,
    )
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)

    return ModelAssignmentResponse.model_validate(assignment)


@router.get("/", response_model=ModelAssignmentListResponse)
async def list_model_assignments(
    db: AsyncSession = Depends(get_db_session_with_rls),
    current_user: dict = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    system_function: Optional[str] = Query(
        None, description="Filter by system function"
    ),
):
    user_id = get_user_id_fromClaims(current_user)

    filters = [ModelAssignment.user_id == user_id]
    if system_function:
        filters.append(ModelAssignment.system_function == system_function)

    count_result = await db.execute(
        select(func.count(ModelAssignment.id)).where(*filters)
    )
    total = count_result.scalar_one()

    result = await db.execute(
        select(ModelAssignment)
        .where(*filters)
        .order_by(ModelAssignment.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    assignments = result.scalars().all()

    return ModelAssignmentListResponse(
        items=[ModelAssignmentResponse.model_validate(a) for a in assignments],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{assignment_id}", response_model=ModelAssignmentResponse)
async def get_model_assignment(
    assignment_id: UUID,
    db: AsyncSession = Depends(get_db_session_with_rls),
    current_user: dict = Depends(get_current_user),
):
    user_id = get_user_id_fromClaims(current_user)

    result = await db.execute(
        select(ModelAssignment).where(
            ModelAssignment.id == assignment_id,
            ModelAssignment.user_id == user_id,
        )
    )
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=404, detail="Model assignment not found")

    return ModelAssignmentResponse.model_validate(assignment)


@router.put("/{assignment_id}", response_model=ModelAssignmentResponse)
async def update_model_assignment(
    assignment_id: UUID,
    payload: ModelAssignmentUpdate,
    db: AsyncSession = Depends(get_db_session_with_rls),
    current_user: dict = Depends(get_current_user),
):
    user_id = get_user_id_fromClaims(current_user)

    result = await db.execute(
        select(ModelAssignment).where(
            ModelAssignment.id == assignment_id,
            ModelAssignment.user_id == user_id,
        )
    )
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=404, detail="Model assignment not found")

    if payload.model_name is not None:
        assignment.model_name = payload.model_name
    if payload.is_active is not None:
        assignment.is_active = payload.is_active
    if payload.provider_id is not None:
        # Validate new provider exists and belongs to user
        provider_result = await db.execute(
            select(LLMProvider).where(
                LLMProvider.id == payload.provider_id,
                LLMProvider.user_id == user_id,
            )
        )
        new_provider = provider_result.scalar_one_or_none()
        if not new_provider:
            raise HTTPException(status_code=404, detail="Provider not found")
        if not new_provider.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot assign to an inactive provider.",
            )
        assignment.provider_id = payload.provider_id

    # If setting is_active=True, deactivate other active for same function
    if payload.is_active is True:
        existing = await db.execute(
            select(ModelAssignment).where(
                ModelAssignment.user_id == user_id,
                ModelAssignment.system_function == assignment.system_function,
                ModelAssignment.is_active == True,
                ModelAssignment.id != assignment_id,
            )
        )
        for other in existing.scalars().all():
            other.is_active = False
        await db.flush()

    await db.commit()
    await db.refresh(assignment)

    return ModelAssignmentResponse.model_validate(assignment)


@router.delete("/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model_assignment(
    assignment_id: UUID,
    db: AsyncSession = Depends(get_db_session_with_rls),
    current_user: dict = Depends(get_current_user),
):
    user_id = get_user_id_fromClaims(current_user)

    result = await db.execute(
        select(ModelAssignment).where(
            ModelAssignment.id == assignment_id,
            ModelAssignment.user_id == user_id,
        )
    )
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=404, detail="Model assignment not found")

    await db.delete(assignment)
    await db.commit()


@router.post("/{assignment_id}/ping", response_model=ModelAssignmentResponse)
async def ping_model_assignment(
    assignment_id: UUID,
    db: AsyncSession = Depends(get_db_session_with_rls),
    current_user: dict = Depends(get_current_user),
):
    ping_start = time.time()
    user_id = get_user_id_fromClaims(current_user)
    logger.info("=== PING START ===")
    logger.info(f"assignment_id={assignment_id} user_id={user_id}")

    t = time.time()
    result = await db.execute(
        select(ModelAssignment).where(
            ModelAssignment.id == assignment_id,
            ModelAssignment.user_id == user_id,
        )
    )
    assignment = result.scalar_one_or_none()
    if not assignment:
        logger.warning(f"PING FAIL: assignment not found id={assignment_id}")
        raise HTTPException(status_code=404, detail="Model assignment not found")
    logger.info(
        f"[1/5] Loaded assignment model_name={assignment.model_name} system_function={assignment.system_function} health_status={assignment.health_status} ({(time.time()-t)*1000:.1f}ms)"
    )

    t = time.time()
    provider_result = await db.execute(
        select(LLMProvider).where(
            LLMProvider.id == assignment.provider_id,
            LLMProvider.user_id == user_id,
        )
    )
    provider = provider_result.scalar_one_or_none()
    if not provider:
        logger.warning(
            f"PING FAIL: provider not found provider_id={assignment.provider_id}"
        )
        raise HTTPException(status_code=404, detail="Associated provider not found")
    logger.info(
        f"[2/5] Loaded provider type={provider.provider_type} base_url={provider.base_url!r} is_active={provider.is_active} has_key={provider.encrypted_api_key is not None} ({(time.time()-t)*1000:.1f}ms)"
    )

    t = time.time()
    api_key = None
    if provider.encrypted_api_key:
        try:
            api_key = await get_provider_api_key(db, user_id, provider.provider_type)
            logger.info(
                f"[3/5] API key resolved (masked={api_key[:8] + '...' if api_key else 'None'}) ({(time.time()-t)*1000:.1f}ms)"
            )
        except Exception as e:
            logger.error(f"[3/5] API key decryption FAILED: {e}", exc_info=True)
            api_key = None
    else:
        logger.info(
            f"[3/5] No encrypted API key — skipping ({(time.time()-t)*1000:.1f}ms)"
        )

    t = time.time()
    logger.info(
        f"[4/5] Calling health_check_model provider_type={provider.provider_type} base_url={provider.base_url!r} model_name={assignment.model_name} timeout=60.0"
    )
    try:
        success, message = await health_check_model(
            provider_type=provider.provider_type,
            base_url=provider.base_url or "",
            api_key=api_key,
            model_name=assignment.model_name,
        )
        elapsed = time.time() - t
        logger.info(
            f"[4/5] health_check_model returned success={success} message={message!r} elapsed={elapsed:.2f}s"
        )
    except Exception as e:
        elapsed = time.time() - t
        logger.error(f"[4/5] health_check_model EXCEPTION: {e}", exc_info=True)
        success, message = False, f"Exception: {e}"

    t2 = time.time()
    assignment.health_status = "verified" if success else "unreachable"
    assignment.health_message = message
    await db.commit()
    await db.refresh(assignment)
    logger.info(
        f"[5/5] Persisted health_status={assignment.health_status} health_message={assignment.health_message!r} ({(time.time()-t2)*1000:.1f}ms)"
    )

    total_elapsed = time.time() - ping_start
    logger.info(f"=== PING END total={total_elapsed:.2f}s ===")

    return ModelAssignmentResponse.model_validate(assignment)
