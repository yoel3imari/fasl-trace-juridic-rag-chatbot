"""
Tests for LLM Provider CRUD endpoints.
"""

import os
import base64
import pytest
import httpx
from httpx import ASGITransport
import jwt
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy import select, func

os.environ.setdefault("ENCRYPTION_KEY", base64.b64encode(os.urandom(32)).decode())

from app.core.config import Settings
from app.models.llm_provider import LLMProvider


def create_test_jwt(user_id: str = None) -> str:
    """Create a valid Supabase JWT for testing."""
    if user_id is None:
        user_id = str(uuid.uuid4())
    secret = Settings().supabase_jwt_secret
    payload = {
        "sub": user_id,
        "email": "test@example.com",
        "exp": 9999999999,
        "iat": 1000000000,
        "role": "authenticated",
        "aud": "authenticated",
    }
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture
def app():
    """Create a fresh app instance for each test."""
    from main import app
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
def user_id() -> str:
    return str(uuid.uuid4())


# ============================================================
# Task 5.1: Test router registration
# ============================================================

@pytest.mark.asyncio
async def test_router_registered(app):
    """Test that the LLM provider router is registered."""
    routes = [str(r) for r in app.routes]
    assert any("llm-provider" in r.lower() for r in routes), "LLM provider routes not found"


# ============================================================
# Task 5.2: Test provider creation validation
# ============================================================

@pytest.mark.asyncio
async def test_create_provider_invalid_type(user_id, app):
    """Test POST with invalid provider_type returns 422."""
    from app.core.database import get_db_session_with_rls
    from app.core.security import get_current_user

    token = create_test_jwt(user_id)

    # Override dependencies with AsyncMock for db session
    mock_db = MagicMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    app.dependency_overrides[get_db_session_with_rls] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: {"user_id": user_id}

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        ac.headers["Authorization"] = f"Bearer {token}"
        response = await ac.post(
            "/api/v1/llm-providers/",
            json={"provider_type": "invalid_provider", "base_url": "https://some.api/v1"},
        )
        assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text}"

    # Restore
    app.dependency_overrides.clear()


# ============================================================
# AC1: Provider creation success path
# ============================================================
@pytest.mark.asyncio
async def test_create_provider_success(user_id, app):
    from app.core.database import get_db_session_with_rls
    from app.core.security import get_current_user

    token = create_test_jwt(user_id)

    fake_id = uuid.UUID(user_id)
    fake_provider = type(
        "FakeProvider",
        (),
        {
            "id": fake_id,
            "user_id": user_id,
            "provider_type": "openai",
            "base_url": "https://enterprise.openai.com/v1",
            "api_version": "v1",
            "encrypted_api_key": None,
            "is_active": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        },
    )()

    mock_db = MagicMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    async def fake_execute(*args, **kwargs):
        result = MagicMock()
        result.scalar_one_or_none = MagicMock(return_value=None)
        result.scalar_one = MagicMock(return_value=0)
        return result

    mock_db.execute = AsyncMock(side_effect=fake_execute)

    app.dependency_overrides[get_db_session_with_rls] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: {"user_id": user_id}

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        ac.headers["Authorization"] = f"Bearer {token}"
        response = await ac.post(
            "/api/v1/llm-providers/",
            json={"provider_type": "openai", "base_url": "https://enterprise.openai.com/v1", "api_version": "v1"},
        )
        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["provider_type"] == "openai"
        assert data["base_url"] == "https://enterprise.openai.com/v1"
        assert data["api_version"] == "v1"
        assert data["is_active"] is True
        assert "id" in data
        assert "user_id" in data

    app.dependency_overrides.clear()


# ============================================================
# Task 5.3: Test provider listing requires auth
# ============================================================

@pytest.mark.asyncio
async def test_list_providers_requires_auth(app):
    """Test GET /api/v1/llm-providers/ without auth returns 401."""
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/api/v1/llm-providers/")
        assert response.status_code == 401


# ============================================================
# Task 5.4: Test provider update returns 404 for non-existent
# ============================================================

@pytest.mark.asyncio
async def test_update_provider_not_found(user_id, app):
    """Test PUT /api/v1/llm-providers/{id} returns 404 for non-existent provider."""
    from app.core.database import get_db_session_with_rls
    from app.core.security import get_current_user

    token = create_test_jwt(user_id)
    non_existent_id = str(uuid.uuid4())

    # Mock DB session to return None (provider not found)
    mock_db = MagicMock()
    mock_execute = MagicMock()
    mock_execute.scalar_one_or_none = MagicMock(return_value=None)
    mock_db.execute = AsyncMock(return_value=mock_execute)

    app.dependency_overrides[get_db_session_with_rls] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: {"user_id": user_id}

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        ac.headers["Authorization"] = f"Bearer {token}"
        response = await ac.put(
            f"/api/v1/llm-providers/{non_existent_id}",
            json={"base_url": "https://new-url.com/v1"},
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"

    app.dependency_overrides.clear()


# ============================================================
@pytest.mark.asyncio
async def test_update_provider_success(user_id, app):
    from app.core.database import get_db_session_with_rls
    from app.core.security import get_current_user

    token = create_test_jwt(user_id)
    provider_id = str(uuid.uuid4())

    fake_provider = type(
        "FakeProvider",
        (),
        {
            "id": uuid.UUID(provider_id),
            "user_id": user_id,
            "provider_type": "openai",
            "base_url": "https://old-url.com/v1",
            "api_version": "v0",
            "is_active": True,
            "encrypted_api_key": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        },
    )()

    mock_db = MagicMock()
    mock_execute = MagicMock()
    mock_execute.scalar_one_or_none = MagicMock(return_value=fake_provider)
    mock_db.execute = AsyncMock(return_value=mock_execute)
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    app.dependency_overrides[get_db_session_with_rls] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: {"user_id": user_id}

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        ac.headers["Authorization"] = f"Bearer {token}"
        response = await ac.put(
            f"/api/v1/llm-providers/{provider_id}",
            json={"base_url": "https://new-url.com/v2", "api_version": "v2", "is_active": False},
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["base_url"] == "https://new-url.com/v2"
        assert data["api_version"] == "v2"
        assert data["is_active"] is False
        assert mock_db.commit.called

    app.dependency_overrides.clear()


# ============================================================
# Task 5.5: Test provider deletion returns 404 for non-existent
# ============================================================
@pytest.mark.asyncio
async def test_update_provider_success(user_id, app):
    """Test PUT updates fields and persists to DB."""
    from app.core.database import get_db_session_with_rls
    from app.core.security import get_current_user

    token = create_test_jwt(user_id)
    provider_id = str(uuid.uuid4())

    fake_provider = type(
        "FakeProvider",
        (),
        {
            "id": uuid.UUID(provider_id),
            "user_id": user_id,
            "provider_type": "openai",
            "base_url": "https://old-url.com/v1",
            "api_version": "v0",
            "is_active": True,
            "encrypted_api_key": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        },
    )()

    mock_db = MagicMock()
    mock_execute = MagicMock()
    mock_execute.scalar_one_or_none = MagicMock(return_value=fake_provider)
    mock_db.execute = AsyncMock(return_value=mock_execute)
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    app.dependency_overrides[get_db_session_with_rls] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: {"user_id": user_id}

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        ac.headers["Authorization"] = f"Bearer {token}"
        response = await ac.put(
            f"/api/v1/llm-providers/{provider_id}",
            json={"base_url": "https://new-url.com/v2", "api_version": "v2", "is_active": False},
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["base_url"] == "https://new-url.com/v2"
        assert data["api_version"] == "v2"
        assert data["is_active"] is False

    app.dependency_overrides.clear()


# ============================================================
# Task 5.5: Test provider deletion returns 404 for non-existent
# ============================================================

@pytest.mark.asyncio
async def test_delete_provider_not_found(user_id, app):
    """Test DELETE /api/v1/llm-providers/{id} returns 404 for non-existent provider."""
    from app.core.database import get_db_session_with_rls
    from app.core.security import get_current_user

    token = create_test_jwt(user_id)
    non_existent_id = str(uuid.uuid4())

    mock_db = MagicMock()
    mock_execute = MagicMock()
    mock_execute.scalar_one_or_none = MagicMock(return_value=None)
    mock_db.execute = AsyncMock(return_value=mock_execute)

    app.dependency_overrides[get_db_session_with_rls] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: {"user_id": user_id}

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        ac.headers["Authorization"] = f"Bearer {token}"
        response = await ac.delete(f"/api/v1/llm-providers/{non_existent_id}")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"

    app.dependency_overrides.clear()


# ============================================================
# Task 5.6: Test RLS isolation
# ============================================================

@pytest.mark.asyncio
async def test_rls_isolation(user_id, app):
    """Test that user B cannot access user A's provider (returns 404)."""
    from app.core.database import get_db_session_with_rls
    from app.core.security import get_current_user

    user_b_id = str(uuid.uuid4())
    provider_id = str(uuid.uuid4())
    token_b = create_test_jwt(user_b_id)

    # Mock DB to return None (provider not found for user B)
    mock_db = MagicMock()
    mock_execute = MagicMock()
    mock_execute.scalar_one_or_none = MagicMock(return_value=None)
    mock_db.execute = AsyncMock(return_value=mock_execute)

    app.dependency_overrides[get_db_session_with_rls] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: {"user_id": user_b_id}

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        ac.headers["Authorization"] = f"Bearer {token_b}"
        response = await ac.get(f"/api/v1/llm-providers/{provider_id}")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"

    app.dependency_overrides.clear()


# ============================================================
# Task 5.7: Test NFR-S1 warning for public endpoints
# ============================================================

@pytest.mark.asyncio
async def test_nfr_s1_warning_endpoint_exists(user_id, app):
    """Test that the create endpoint handles public endpoints correctly."""
    from app.core.database import get_db_session_with_rls
    from app.core.security import get_current_user
    from app.api.v1.router_llm_provider import check_public_endpoint_warning

    token = create_test_jwt(user_id)

    # Test the warning function directly
    warning = check_public_endpoint_warning("https://api.openai.com/v1")
    assert warning is not None, "Should warn about public OpenAI endpoint"
    assert "api.openai.com" in warning or "Warning" in warning

    warning_none = check_public_endpoint_warning(None)
    assert warning_none is None, "Should not warn for None base_url"

    warning_safe = check_public_endpoint_warning("https://my-enterprise-openai.com/v1")
    assert warning_safe is None, "Should not warn for non-public endpoints"

    app.dependency_overrides.clear()


# ============================================================
# Story 2.2: API Key Management Tests
# ============================================================


@pytest.mark.asyncio
async def test_decrypt_service_roundtrip():
    """Test that encrypt then decrypt returns original plaintext."""
    from app.services.crypto_service import encrypt_api_key, decrypt_api_key

    original = "sk-test-key-1234567890abcdef"
    encrypted = encrypt_api_key(original)
    decrypted = decrypt_api_key(encrypted)
    assert decrypted == original, f"Roundtrip failed: {original} != {decrypted}"
    assert original not in encrypted, "Encrypted value must not contain plaintext"


def test_mask_service_formats_correctly():
    """Test mask_api_key produces correct format."""
    from app.services.crypto_service import mask_api_key

    assert mask_api_key("sk-test-key-1234567890abcdef") == "sk-t...cdef"
    assert mask_api_key("abc") == "***"
    assert mask_api_key("12345678") == "********"


@pytest.mark.asyncio
async def test_set_api_key_encrypts(user_id, app):
    """Test POST api-key stores encrypted value and returns masked representation."""
    from app.core.database import get_db_session_with_rls
    from app.core.security import get_current_user

    token = create_test_jwt(user_id)
    provider_id = str(uuid.uuid4())

    fake_id = uuid.UUID(provider_id)

    class FakeProvider:
        id = fake_id
        user_id = user_id
        encrypted_api_key = None
        updated_at = datetime.now(timezone.utc)

    mock_db = MagicMock()
    mock_execute = MagicMock()
    mock_execute.scalar_one_or_none = MagicMock(return_value=FakeProvider())
    mock_db.execute = AsyncMock(return_value=mock_execute)
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    app.dependency_overrides[get_db_session_with_rls] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: {"user_id": user_id}

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        ac.headers["Authorization"] = f"Bearer {token}"
        response = await ac.post(
            f"/api/v1/llm-providers/{provider_id}/api-key",
            json={"api_key": "sk-test-key-12345"},
        )
        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["has_api_key"] is True
        assert data["masked_key"] is not None
        assert "sk-test-key-12345" not in str(data), "Raw key must never appear in response"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_api_key_masked(user_id, app):
    """Test GET api-key returns masked representation, never raw key."""
    from app.core.database import get_db_session_with_rls
    from app.core.security import get_current_user
    from app.services.crypto_service import encrypt_api_key

    token = create_test_jwt(user_id)
    provider_id = str(uuid.uuid4())

    plaintext = "sk-my-secret-key-998877"
    encrypted = encrypt_api_key(plaintext)

    class FakeProvider:
        id = uuid.UUID(provider_id)
        user_id = user_id
        encrypted_api_key = encrypted
        updated_at = datetime.now(timezone.utc)

    mock_db = MagicMock()
    mock_execute = MagicMock()
    mock_execute.scalar_one_or_none = MagicMock(return_value=FakeProvider())
    mock_db.execute = AsyncMock(return_value=mock_execute)

    app.dependency_overrides[get_db_session_with_rls] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: {"user_id": user_id}

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        ac.headers["Authorization"] = f"Bearer {token}"
        response = await ac.get(f"/api/v1/llm-providers/{provider_id}/api-key")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["has_api_key"] is True
        assert data["masked_key"] is not None
        assert plaintext not in str(data), "Raw key must NEVER appear in response"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_key_rotation(user_id, app):
    """Test POST updates encrypted API key (rotation)."""
    from app.core.database import get_db_session_with_rls
    from app.core.security import get_current_user
    from app.services.crypto_service import encrypt_api_key

    token = create_test_jwt(user_id)
    provider_id = str(uuid.uuid4())

    old_key = "sk-old-key-11111"
    new_key = "sk-new-key-22222"
    encrypted_old = encrypt_api_key(old_key)

    class FakeProvider:
        id = uuid.UUID(provider_id)
        user_id = user_id
        encrypted_api_key = encrypted_old
        updated_at = datetime.now(timezone.utc)

    mock_db = MagicMock()
    mock_execute = MagicMock()
    mock_execute.scalar_one_or_none = MagicMock(return_value=FakeProvider())
    mock_db.execute = AsyncMock(return_value=mock_execute)
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    app.dependency_overrides[get_db_session_with_rls] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: {"user_id": user_id}

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        ac.headers["Authorization"] = f"Bearer {token}"
        response = await ac.post(
            f"/api/v1/llm-providers/{provider_id}/api-key",
            json={"api_key": new_key},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["has_api_key"] is True
        assert new_key not in str(data), "Raw new key must never appear in response"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_delete_api_key(user_id, app):
    """Test DELETE api-key sets encrypted_api_key to None."""
    from app.core.database import get_db_session_with_rls
    from app.core.security import get_current_user
    from app.services.crypto_service import encrypt_api_key

    token = create_test_jwt(user_id)
    provider_id = str(uuid.uuid4())

    class FakeProvider:
        id = uuid.UUID(provider_id)
        user_id = user_id
        encrypted_api_key = encrypt_api_key("sk-key-to-delete")
        updated_at = datetime.now(timezone.utc)

    mock_db = MagicMock()
    mock_execute = MagicMock()
    mock_execute.scalar_one_or_none = MagicMock(return_value=FakeProvider())
    mock_db.execute = AsyncMock(return_value=mock_execute)
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    app.dependency_overrides[get_db_session_with_rls] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: {"user_id": user_id}

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        ac.headers["Authorization"] = f"Bearer {token}"
        response = await ac.delete(f"/api/v1/llm-providers/{provider_id}/api-key")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["has_api_key"] is False
        assert data["masked_key"] is None

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_key_endpoints_require_auth(app):
    """Test api-key endpoints return 401 without auth."""
    provider_id = str(uuid.uuid4())

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        post_resp = await ac.post(f"/api/v1/llm-providers/{provider_id}/api-key", json={"api_key": "sk-test"})
        assert post_resp.status_code == 401

        get_resp = await ac.get(f"/api/v1/llm-providers/{provider_id}/api-key")
        assert get_resp.status_code == 401

        delete_resp = await ac.delete(f"/api/v1/llm-providers/{provider_id}/api-key")
        assert delete_resp.status_code == 401


@pytest.mark.asyncio
async def test_api_key_endpoints_404_for_nonexistent_provider(user_id, app):
    """Test api-key endpoints return 404 for non-existent provider."""
    from app.core.database import get_db_session_with_rls
    from app.core.security import get_current_user

    token = create_test_jwt(user_id)
    non_existent_id = str(uuid.uuid4())

    mock_db = MagicMock()
    mock_execute = MagicMock()
    mock_execute.scalar_one_or_none = MagicMock(return_value=None)
    mock_db.execute = AsyncMock(return_value=mock_execute)

    app.dependency_overrides[get_db_session_with_rls] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: {"user_id": user_id}

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        ac.headers["Authorization"] = f"Bearer {token}"

        post_resp = await ac.post(f"/api/v1/llm-providers/{non_existent_id}/api-key", json={"api_key": "sk-test"})
        assert post_resp.status_code == 404

        get_resp = await ac.get(f"/api/v1/llm-providers/{non_existent_id}/api-key")
        assert get_resp.status_code == 404

        delete_resp = await ac.delete(f"/api/v1/llm-providers/{non_existent_id}/api-key")
        assert delete_resp.status_code == 404

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_provider_response_includes_has_api_key():
    """Test LLMProviderResponse includes has_api_key without leaking encrypted data."""
    from app.schemas.llm_provider import LLMProviderResponse
    from app.services.crypto_service import encrypt_api_key

    now = datetime.now(timezone.utc)
    data = {
        "id": str(uuid.uuid4()),
        "user_id": str(uuid.uuid4()),
        "provider_type": "openai",
        "base_url": "https://enterprise.openai.com/v1",
        "api_version": "v1",
        "has_api_key": True,
        "is_active": True,
        "warning": None,
        "created_at": now,
        "updated_at": now,
    }

    response = LLMProviderResponse(**data)
    assert response.has_api_key is True

    dumped = response.model_dump()
    assert "encrypted_api_key" not in dumped, "encrypted_api_key must never leak in responses"
    assert "api_key" not in dumped, "api_key must never leak in responses"
