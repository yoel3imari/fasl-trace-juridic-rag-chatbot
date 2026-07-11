"""
JWT verification dependency — local verification using PyJWT.

Uses the Supabase JWT secret for sub-millisecond local token verification
instead of making a network round-trip to Supabase's auth endpoint.
This satisfies NFR-P1 (<200ms TTFB).
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt

from app.core.config import get_settings, Settings

security_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    Decode and verify a Supabase JWT. Returns the decoded payload
    containing the user's `sub` (user_id) claim.

    Raises 401 if the token is invalid, expired, or missing.
    """
    token = credentials.credentials

    if not settings.supabase_jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SUPABASE_JWT_SECRET is not configured",
        )

    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing 'sub' claim",
        )

    return {"user_id": user_id, "payload": payload}


async def require_admin(
    current_user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    Guard dependency that allows only admin users to proceed.

    Admin status is resolved from the JWT in this order:
      1. ``app_metadata.role == "admin"`` (Supabase convention)
      2. top-level ``role == "admin"`` claim
      3. ``settings.admin_user_ids`` allowlist (config override)

    Raises 403 if the caller is not an admin.

    Security note: every route using this dependency should pair it with
    a non-RLS service session (``get_db_session_service``) for any shared
    writes (e.g. system-corpus ingestion).
    """
    payload = current_user.get("payload", {})

    app_metadata = payload.get("app_metadata") or {}
    if isinstance(app_metadata, dict) and app_metadata.get("role") == "admin":
        return current_user

    if payload.get("role") == "admin":
        return current_user

    admin_ids = [uid.strip() for uid in (getattr(settings, "admin_user_ids", "") or "").split(",") if uid.strip()]
    if current_user.get("user_id") in admin_ids:
        return current_user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Admin privileges required.",
    )
