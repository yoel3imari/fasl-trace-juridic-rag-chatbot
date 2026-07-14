"""
JWT verification dependency — local verification using PyJWT.

Uses Supabase's JWKS endpoint to fetch the public key and verify
the token locally. This avoids a network round-trip to the Auth
server on every request while supporting ES256-signed tokens
(modern Supabase default) and falling back to HS256 for older
projects that use the JWT secret.
"""

from urllib.parse import urlparse

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from jwt import PyJWKClient, PyJWKClientError

from app.core.config import get_settings, Settings

security_scheme = HTTPBearer()

# Cached JWKS client — constructed lazily on first use
_jwks_client: PyJWKClient | None = None


def _get_jwks_client(supabase_url: str) -> PyJWKClient:
    """Build and cache a PyJWKClient from the Supabase project URL."""
    global _jwks_client
    if _jwks_client is not None:
        return _jwks_client

    # supabase_url looks like "https://<project>.supabase.co/rest/v1/"
    parsed = urlparse(supabase_url)
    jwks_url = f"{parsed.scheme}://{parsed.netloc}/auth/v1/.well-known/jwks.json"
    _jwks_client = PyJWKClient(jwks_url, cache_keys=True)
    return _jwks_client


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    Decode and verify a Supabase JWT using the project's JWKS endpoint.

    Returns the decoded payload containing the user's ``sub`` (user_id) claim.

    Raises 401 if the token is invalid, expired, or missing.
    """
    token = credentials.credentials

    # Try ES256 via JWKS first (modern Supabase default)
    try:
        jwks_client = _get_jwks_client(settings.supabase_url)
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=[signing_key.algorithm_name],
            audience="authenticated",
        )
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing 'sub' claim",
            )
        return {"user_id": user_id, "payload": payload}
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except (jwt.InvalidTokenError, PyJWKClientError):
        pass  # Fall through to HS256 attempt below

    # Fallback: HS256 with JWT secret (older Supabase projects)
    if not settings.supabase_jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: not verifiable with JWKS or JWT secret",
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
