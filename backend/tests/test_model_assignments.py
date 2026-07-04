"""
Tests for Model Assignment CRUD endpoints and service functions.
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
# Helper: create a FakeProvider with standard defaults
# ============================================================

def make_fake_provider(
    provider_id: str = None,
    user_id: str = None,
    provider_type: str = "openai",
    base_url: str = "https://enterprise.openai.com/v1",
    is_active: bool = True,
    encrypted_api_key: str = None,
    api_version: str = "v1",
) -> object:
    """Create a fake provider object matching LLMProvider attributes."""
    if provider_id is None:
        provider_id = str(uuid.uuid4())
    return type(
        "FakeProvider",
        (),
        {
            "id": uuid.UUID(provider_id),
            "user_id": user_id,
            "provider_type": provider_type,
            "base_url": base_url,
            "api_version": api_version,
            "encrypted_api_key": encrypted_api_key,
            "is_active": is_active,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        },
    )()


def make_fake_assignment(
    assignment_id: str = None,
    user_id: str = None,
    provider_id: str = None,
    model_name: str = "gpt-4o",
    system_function: str = "generation",
    is_active: bool = True,
    health_status: str = None,
    health_message: str = None,
) -> dict:
    """Create a fake ModelAssignment dict matching model attributes."""
    if assignment_id is None:
        assignment_id = str(uuid.uuid4())
    if provider_id is None:
        provider_id = str(uuid.uuid4())
    return {
        "id": uuid.UUID(assignment_id),
        "user_id": uuid.UUID(user_id) if isinstance(user_id, str) else user_id,
        "provider_id": uuid.UUID(provider_id) if isinstance(provider_id, str) else provider_id,
        "model_name": model_name,
        "system_function": system_function,
        "is_active": is_active,
        "health_status": health_status,
        "health_message": health_message,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }


def make_fake_assignment_object(
    assignment_id: str = None,
    user_id: str = None,
    provider_id: str = None,
    model_name: str = "gpt-4o",
    system_function: str = "generation",
    is_active: bool = True,
    health_status: str = None,
    health_message: str = None,
) -> object:
    """Create a fake ModelAssignment object (for tests that need attribute mutation)."""
    if assignment_id is None:
        assignment_id = str(uuid.uuid4())
    if provider_id is None:
        provider_id = str(uuid.uuid4())
    return type(
        "FakeAssignment",
        (),
        {
            "id": uuid.UUID(assignment_id),
            "user_id": uuid.UUID(user_id) if isinstance(user_id, str) else user_id,
            "provider_id": uuid.UUID(provider_id) if isinstance(provider_id, str) else provider_id,
            "model_name": model_name,
            "system_function": system_function,
            "is_active": is_active,
            "health_status": health_status,
            "health_message": health_message,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        },
    )()


def make_refresh_populate(now: datetime = None):
    """Return an AsyncMock side_effect that populates server-default fields on refresh."""
    if now is None:
        now = datetime.now(timezone.utc)

    async def refresh_side_effect(instance):
        if not hasattr(instance, "id") or instance.id is None:
            instance.id = uuid.uuid4()
        if not hasattr(instance, "created_at") or instance.created_at is None:
            instance.created_at = now
        if not hasattr(instance, "updated_at") or instance.updated_at is None:
            instance.updated_at = now

    return refresh_side_effect


# ============================================================
# Test 1: Create model assignment success
# ============================================================

@pytest.mark.asyncio
async def test_create_model_assignment_success(user_id, app):
    """Test POST /model-assignments/ creates a new assignment with health check."""
    from app.core.database import get_db_session_with_rls
    from app.core.security import get_current_user
    from unittest.mock import patch

    token = create_test_jwt(user_id)
    provider_id = str(uuid.uuid4())

    fake_provider = make_fake_provider(
        provider_id=provider_id,
        user_id=user_id,
        provider_type="openai",
        base_url="https://enterprise.openai.com/v1",
        is_active=True,
        encrypted_api_key=None,
    )

    # Track calls to mock_db.execute
    call_count = [0]

    async def fake_execute(*args, **kwargs):
        call_count[0] += 1
        result = MagicMock()
        if call_count[0] == 1:
            # First call: find provider
            result.scalar_one_or_none = MagicMock(return_value=fake_provider)
        elif call_count[0] == 2:
            # Second call: find existing active assignments
            result.scalars = MagicMock()
            result.scalars.return_value.all = MagicMock(return_value=[])
        else:
            # Subsequent calls (e.g. after commit/refresh)
            result.scalar_one_or_none = MagicMock(return_value=None)
            result.scalars = MagicMock()
            result.scalars.return_value.all = MagicMock(return_value=[])
        return result

    mock_db = MagicMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock(side_effect=make_refresh_populate())
    mock_db.flush = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=fake_execute)

    app.dependency_overrides[get_db_session_with_rls] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: {"user_id": user_id}

    with patch("app.api.v1.router_model_assignment.health_check_model", new_callable=AsyncMock) as mock_health:
        mock_health.return_value = (True, "verified")

        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            ac.headers["Authorization"] = f"Bearer {token}"
            response = await ac.post(
                "/api/v1/model-assignments/",
                json={
                    "provider_id": provider_id,
                    "model_name": "gpt-4o",
                    "system_function": "generation",
                },
            )
            assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
            data = response.json()
            assert data["model_name"] == "gpt-4o"
            assert data["system_function"] == "generation"
            assert data["is_active"] is True
            assert data["health_status"] == "verified"
            assert "id" in data
            assert "user_id" in data

    app.dependency_overrides.clear()


# ============================================================
# Test 2: Create assignment deactivates previous
# ============================================================

@pytest.mark.asyncio
async def test_create_assignment_deactivates_previous(user_id, app):
    """Test AC 3: Creating a new active assignment deactivates the previous one."""
    from app.core.database import get_db_session_with_rls
    from app.core.security import get_current_user
    from unittest.mock import patch

    token = create_test_jwt(user_id)
    provider_id = str(uuid.uuid4())

    fake_provider = make_fake_provider(
        provider_id=provider_id,
        user_id=user_id,
        is_active=True,
    )

    existing_assignment = make_fake_assignment_object(
        user_id=user_id,
        provider_id=provider_id,
        model_name="gpt-4o",
        system_function="generation",
        is_active=True,
    )

    call_count = [0]

    async def fake_execute(*args, **kwargs):
        call_count[0] += 1
        result = MagicMock()
        if call_count[0] == 1:
            # First call: find provider
            result.scalar_one_or_none = MagicMock(return_value=fake_provider)
        elif call_count[0] == 2:
            # Second call: find existing active assignments
            result.scalars = MagicMock()
            result.scalars.return_value.all = MagicMock(return_value=[existing_assignment])
        else:
            result.scalar_one_or_none = MagicMock(return_value=None)
            result.scalars = MagicMock()
            result.scalars.return_value.all = MagicMock(return_value=[])
        return result

    mock_db = MagicMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock(side_effect=make_refresh_populate())
    mock_db.flush = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=fake_execute)

    app.dependency_overrides[get_db_session_with_rls] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: {"user_id": user_id}

    with patch("app.api.v1.router_model_assignment.health_check_model", new_callable=AsyncMock) as mock_health:
        mock_health.return_value = (True, "verified")

        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            ac.headers["Authorization"] = f"Bearer {token}"
            response = await ac.post(
                "/api/v1/model-assignments/",
                json={
                    "provider_id": provider_id,
                    "model_name": "gpt-4o",
                    "system_function": "generation",
                },
            )
            assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
            data = response.json()
            assert data["is_active"] is True
            assert data["model_name"] == "gpt-4o"
            # Verify the old assignment was deactivated
            assert existing_assignment.is_active is False

    app.dependency_overrides.clear()


# ============================================================
# Test 3: Create assignment with nonexistent provider
# ============================================================

@pytest.mark.asyncio
async def test_create_assignment_nonexistent_provider(user_id, app):
    """Test POST with invalid provider_id returns 404."""
    from app.core.database import get_db_session_with_rls
    from app.core.security import get_current_user

    token = create_test_jwt(user_id)
    provider_id = str(uuid.uuid4())

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
        response = await ac.post(
            "/api/v1/model-assignments/",
            json={
                "provider_id": provider_id,
                "model_name": "gpt-4o",
                "system_function": "generation",
            },
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"

    app.dependency_overrides.clear()


# ============================================================
# Test 4: Create assignment with inactive provider
# ============================================================

@pytest.mark.asyncio
async def test_create_assignment_inactive_provider(user_id, app):
    """Test POST with inactive provider returns 400."""
    from app.core.database import get_db_session_with_rls
    from app.core.security import get_current_user

    token = create_test_jwt(user_id)
    provider_id = str(uuid.uuid4())

    fake_provider = make_fake_provider(
        provider_id=provider_id,
        user_id=user_id,
        is_active=False,
    )

    mock_db = MagicMock()
    mock_execute = MagicMock()
    mock_execute.scalar_one_or_none = MagicMock(return_value=fake_provider)
    mock_db.execute = AsyncMock(return_value=mock_execute)

    app.dependency_overrides[get_db_session_with_rls] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: {"user_id": user_id}

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        ac.headers["Authorization"] = f"Bearer {token}"
        response = await ac.post(
            "/api/v1/model-assignments/",
            json={
                "provider_id": provider_id,
                "model_name": "gpt-4o",
                "system_function": "generation",
            },
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        assert "inactive" in response.text.lower()

    app.dependency_overrides.clear()


# ============================================================
# Test 5: Create assignment with invalid system_function
# ============================================================

@pytest.mark.asyncio
async def test_create_assignment_invalid_system_function(user_id, app):
    """Test POST with invalid system_function returns 422 (Pydantic validation)."""
    from app.core.database import get_db_session_with_rls
    from app.core.security import get_current_user

    token = create_test_jwt(user_id)
    provider_id = str(uuid.uuid4())

    # Mock DB is not needed — 422 happens at schema validation before endpoint body
    mock_db = MagicMock()
    app.dependency_overrides[get_db_session_with_rls] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: {"user_id": user_id}

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        ac.headers["Authorization"] = f"Bearer {token}"
        response = await ac.post(
            "/api/v1/model-assignments/",
            json={
                "provider_id": provider_id,
                "model_name": "gpt-4o",
                "system_function": "invalid",
            },
        )
        assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text}"

    app.dependency_overrides.clear()


# ============================================================
# Test 6: Health check returns status
# ============================================================

@pytest.mark.asyncio
async def test_health_check_returns_status(user_id, app):
    """Test AC 2: Assignment creation returns health_status from health check."""
    from app.core.database import get_db_session_with_rls
    from app.core.security import get_current_user
    from unittest.mock import patch

    token = create_test_jwt(user_id)
    provider_id = str(uuid.uuid4())

    fake_provider = make_fake_provider(
        provider_id=provider_id,
        user_id=user_id,
        is_active=True,
    )

    call_count = [0]

    async def fake_execute(*args, **kwargs):
        call_count[0] += 1
        result = MagicMock()
        if call_count[0] == 1:
            result.scalar_one_or_none = MagicMock(return_value=fake_provider)
        elif call_count[0] == 2:
            result.scalars = MagicMock()
            result.scalars.return_value.all = MagicMock(return_value=[])
        else:
            result.scalar_one_or_none = MagicMock(return_value=None)
            result.scalars = MagicMock()
            result.scalars.return_value.all = MagicMock(return_value=[])
        return result

    mock_db = MagicMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock(side_effect=make_refresh_populate())
    mock_db.flush = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=fake_execute)

    app.dependency_overrides[get_db_session_with_rls] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: {"user_id": user_id}

    with patch("app.api.v1.router_model_assignment.health_check_model", new_callable=AsyncMock) as mock_health:
        mock_health.return_value = (True, "verified")

        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            ac.headers["Authorization"] = f"Bearer {token}"
            response = await ac.post(
                "/api/v1/model-assignments/",
                json={
                    "provider_id": provider_id,
                    "model_name": "gpt-4o",
                    "system_function": "generation",
                },
            )
            assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
            data = response.json()
            assert data["health_status"] == "verified"

    app.dependency_overrides.clear()


# ============================================================
# Test 7: List assignments with filter
# ============================================================

@pytest.mark.asyncio
async def test_list_assignments_with_filter(user_id, app):
    """Test GET /model-assignments/?system_function=generation returns filtered list."""
    from app.core.database import get_db_session_with_rls
    from app.core.security import get_current_user

    token = create_test_jwt(user_id)
    provider_id = str(uuid.uuid4())

    fake_assignment = make_fake_assignment(
        user_id=user_id,
        provider_id=provider_id,
        model_name="gpt-4o",
        system_function="generation",
        is_active=True,
    )

    call_count = [0]

    async def fake_execute(*args, **kwargs):
        call_count[0] += 1
        result = MagicMock()
        if call_count[0] == 1:
            # First call: count query
            result.scalar_one = MagicMock(return_value=1)
        elif call_count[0] == 2:
            # Second call: list query
            result.scalars = MagicMock()
            result.scalars.return_value.all = MagicMock(return_value=[fake_assignment])
        else:
            result.scalar_one = MagicMock(return_value=0)
            result.scalars = MagicMock()
            result.scalars.return_value.all = MagicMock(return_value=[])
        return result

    mock_db = MagicMock()
    mock_db.execute = AsyncMock(side_effect=fake_execute)

    app.dependency_overrides[get_db_session_with_rls] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: {"user_id": user_id}

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        ac.headers["Authorization"] = f"Bearer {token}"
        response = await ac.get("/api/v1/model-assignments/?system_function=generation")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "items" in data
        assert len(data["items"]) == 1
        assert data["items"][0]["system_function"] == "generation"
        assert data["total"] == 1

    app.dependency_overrides.clear()


# ============================================================
# Test 8: Get single assignment
# ============================================================

@pytest.mark.asyncio
async def test_get_single_assignment(user_id, app):
    """Test GET /model-assignments/{id} returns the assignment."""
    from app.core.database import get_db_session_with_rls
    from app.core.security import get_current_user

    token = create_test_jwt(user_id)
    assignment_id = str(uuid.uuid4())
    provider_id = str(uuid.uuid4())

    fake_assignment = make_fake_assignment(
        assignment_id=assignment_id,
        user_id=user_id,
        provider_id=provider_id,
        model_name="gpt-4o",
        system_function="generation",
        is_active=True,
        health_status="verified",
    )

    mock_db = MagicMock()
    mock_execute = MagicMock()
    mock_execute.scalar_one_or_none = MagicMock(return_value=fake_assignment)
    mock_db.execute = AsyncMock(return_value=mock_execute)

    app.dependency_overrides[get_db_session_with_rls] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: {"user_id": user_id}

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        ac.headers["Authorization"] = f"Bearer {token}"
        response = await ac.get(f"/api/v1/model-assignments/{assignment_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["model_name"] == "gpt-4o"
        assert data["system_function"] == "generation"
        assert data["is_active"] is True
        assert data["health_status"] == "verified"
        assert "id" in data
        assert "user_id" in data

    app.dependency_overrides.clear()


# ============================================================
# Test 9: Get assignment not found
# ============================================================

@pytest.mark.asyncio
async def test_get_assignment_not_found(user_id, app):
    """Test GET /model-assignments/{id} returns 404 for non-existent assignment."""
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
        response = await ac.get(f"/api/v1/model-assignments/{non_existent_id}")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"

    app.dependency_overrides.clear()


# ============================================================
# Test 10: RLS isolation
# ============================================================

@pytest.mark.asyncio
async def test_rls_isolation(user_id, app):
    """Test that user B cannot access user A's assignment (returns 404)."""
    from app.core.database import get_db_session_with_rls
    from app.core.security import get_current_user

    user_b_id = str(uuid.uuid4())
    assignment_id = str(uuid.uuid4())
    token_b = create_test_jwt(user_b_id)

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
        response = await ac.get(f"/api/v1/model-assignments/{assignment_id}")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"

    app.dependency_overrides.clear()


# ============================================================
# Test 11: Update assignment reactivates, deactivates others
# ============================================================

@pytest.mark.asyncio
async def test_update_assignment_reactivates_deactivates_others(user_id, app):
    """Test PUT is_active=true on an inactive assignment deactivates siblings."""
    from app.core.database import get_db_session_with_rls
    from app.core.security import get_current_user

    token = create_test_jwt(user_id)
    assignment_id = str(uuid.uuid4())
    provider_id = str(uuid.uuid4())

    # The assignment we're updating — currently inactive
    target_assignment = make_fake_assignment_object(
        assignment_id=assignment_id,
        user_id=user_id,
        provider_id=provider_id,
        model_name="gpt-4o",
        system_function="retrieval",
        is_active=False,
    )

    # The sibling that is currently active — should be deactivated
    sibling_assignment = make_fake_assignment_object(
        user_id=user_id,
        provider_id=provider_id,
        model_name="claude-3-5-sonnet",
        system_function="retrieval",
        is_active=True,
    )

    call_count = [0]

    async def fake_execute(*args, **kwargs):
        call_count[0] += 1
        result = MagicMock()
        if call_count[0] == 1:
            # First call: find the assignment to update
            result.scalar_one_or_none = MagicMock(return_value=target_assignment)
        elif call_count[0] == 2:
            # Second call: find siblings to deactivate
            result.scalars = MagicMock()
            result.scalars.return_value.all = MagicMock(return_value=[sibling_assignment])
        else:
            result.scalar_one_or_none = MagicMock(return_value=None)
            result.scalars = MagicMock()
            result.scalars.return_value.all = MagicMock(return_value=[])
        return result

    mock_db = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock(side_effect=make_refresh_populate())
    mock_db.flush = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=fake_execute)

    app.dependency_overrides[get_db_session_with_rls] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: {"user_id": user_id}

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        ac.headers["Authorization"] = f"Bearer {token}"
        response = await ac.put(
            f"/api/v1/model-assignments/{assignment_id}",
            json={"is_active": True},
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["is_active"] is True
        # Verify sibling was deactivated
        assert sibling_assignment.is_active is False

    app.dependency_overrides.clear()


# ============================================================
# Test 12: Delete assignment
# ============================================================

@pytest.mark.asyncio
async def test_delete_assignment(user_id, app):
    """Test DELETE /model-assignments/{id} returns 204."""
    from app.core.database import get_db_session_with_rls
    from app.core.security import get_current_user

    token = create_test_jwt(user_id)
    assignment_id = str(uuid.uuid4())
    provider_id = str(uuid.uuid4())

    fake_assignment = make_fake_assignment(
        assignment_id=assignment_id,
        user_id=user_id,
        provider_id=provider_id,
    )

    mock_db = MagicMock()
    mock_execute = MagicMock()
    mock_execute.scalar_one_or_none = MagicMock(return_value=fake_assignment)
    mock_db.execute = AsyncMock(return_value=mock_execute)
    mock_db.delete = AsyncMock()
    mock_db.commit = AsyncMock()

    app.dependency_overrides[get_db_session_with_rls] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: {"user_id": user_id}

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        ac.headers["Authorization"] = f"Bearer {token}"
        response = await ac.delete(f"/api/v1/model-assignments/{assignment_id}")
        assert response.status_code == 204, f"Expected 204, got {response.status_code}: {response.text}"

    app.dependency_overrides.clear()


# ============================================================
# Test 13: Endpoints require auth
# ============================================================

@pytest.mark.asyncio
async def test_endpoint_requires_auth(app):
    """Test all model-assignment endpoints return 401 without JWT."""
    assignment_id = str(uuid.uuid4())
    provider_id = str(uuid.uuid4())

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        post_resp = await ac.post(
            "/api/v1/model-assignments/",
            json={"provider_id": provider_id, "model_name": "gpt-4o", "system_function": "generation"},
        )
        assert post_resp.status_code == 401, f"Expected 401, got {post_resp.status_code}"

        get_resp = await ac.get(f"/api/v1/model-assignments/{assignment_id}")
        assert get_resp.status_code == 401, f"Expected 401, got {get_resp.status_code}"

        list_resp = await ac.get("/api/v1/model-assignments/")
        assert list_resp.status_code == 401, f"Expected 401, got {list_resp.status_code}"

        put_resp = await ac.put(
            f"/api/v1/model-assignments/{assignment_id}",
            json={"is_active": False},
        )
        assert put_resp.status_code == 401, f"Expected 401, got {put_resp.status_code}"

        delete_resp = await ac.delete(f"/api/v1/model-assignments/{assignment_id}")
        assert delete_resp.status_code == 401, f"Expected 401, got {delete_resp.status_code}"


# ============================================================
# Test 14: resolve_active_model returns config
# ============================================================

@pytest.mark.asyncio
async def test_resolve_active_model_returns_config():
    """Test resolve_active_model() returns correct config dict with decrypted API key."""
    from app.services.llm_service import resolve_active_model
    from app.services.crypto_service import encrypt_api_key

    user_id = uuid.uuid4()
    provider_id = uuid.uuid4()
    assignment_id = uuid.uuid4()

    plaintext_key = "sk-test-key-resolve-12345"
    encrypted_key = encrypt_api_key(plaintext_key)

    fake_assignment = make_fake_assignment_object(
        assignment_id=str(assignment_id),
        user_id=str(user_id),
        provider_id=str(provider_id),
        model_name="gpt-4o",
        system_function="generation",
        is_active=True,
    )

    fake_provider = make_fake_provider(
        provider_id=str(provider_id),
        user_id=str(user_id),
        provider_type="openai",
        base_url="https://enterprise.openai.com/v1",
        is_active=True,
        encrypted_api_key=encrypted_key,
    )

    # Mock DB to return a tuple (assignment, provider)
    mock_db = MagicMock()
    mock_result = MagicMock()
    mock_result.one_or_none = MagicMock(return_value=(fake_assignment, fake_provider))
    mock_db.execute = AsyncMock(return_value=mock_result)

    result = await resolve_active_model(mock_db, user_id, "generation")
    assert result is not None
    assert result["model_name"] == "gpt-4o"
    assert result["provider_type"] == "openai"
    assert result["base_url"] == "https://enterprise.openai.com/v1"
    assert result["api_key"] == plaintext_key
    assert result["provider_id"] == str(provider_id)


# ============================================================
# Test 15: resolve_active_model returns None
# ============================================================

@pytest.mark.asyncio
async def test_resolve_active_model_returns_none():
    """Test resolve_active_model() returns None when no match found."""
    from app.services.llm_service import resolve_active_model

    user_id = uuid.uuid4()

    mock_db = MagicMock()
    mock_result = MagicMock()
    mock_result.one_or_none = MagicMock(return_value=None)
    mock_db.execute = AsyncMock(return_value=mock_result)

    result = await resolve_active_model(mock_db, user_id, "generation")
    assert result is None


# ============================================================
# Test 16: get_all_active_assignments returns dict with all 3 functions
# ============================================================

@pytest.mark.asyncio
async def test_get_all_active_assignments():
    """Test get_all_active_assignments() returns dict with all 3 function keys."""
    from app.services.llm_service import get_all_active_assignments, resolve_active_model
    from app.services.crypto_service import encrypt_api_key

    user_id = uuid.uuid4()
    provider_id = uuid.uuid4()

    plaintext_key = "sk-test-key-all-99999"
    encrypted_key = encrypt_api_key(plaintext_key)

    fake_assignment = make_fake_assignment_object(
        user_id=str(user_id),
        provider_id=str(provider_id),
        model_name="gpt-4o",
        system_function="generation",
        is_active=True,
    )

    fake_provider = make_fake_provider(
        provider_id=str(provider_id),
        user_id=str(user_id),
        provider_type="openai",
        base_url="https://enterprise.openai.com/v1",
        is_active=True,
        encrypted_api_key=encrypted_key,
    )

    mock_db = MagicMock()
    mock_result = MagicMock()
    mock_result.one_or_none = MagicMock(return_value=(fake_assignment, fake_provider))
    mock_db.execute = AsyncMock(return_value=mock_result)

    result = await get_all_active_assignments(mock_db, user_id)
    assert isinstance(result, dict)
    assert set(result.keys()) == {"retrieval", "generation", "evaluation"}
    # All three should return the same config since our mock always returns the same tuple
    for func_name in ["retrieval", "generation", "evaluation"]:
        assert result[func_name] is not None
        assert result[func_name]["model_name"] == "gpt-4o"
        assert result[func_name]["provider_type"] == "openai"
        assert result[func_name]["api_key"] == plaintext_key
