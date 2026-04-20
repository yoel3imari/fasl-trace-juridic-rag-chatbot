"""
Document upload endpoint tests.
"""

import io
import os
import jwt
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from httpx import ASGITransport, AsyncClient

from main import app


def create_test_jwt():
    """Create a mock Supabase JWT for testing."""
    # Use the same secret from .env file
    secret = "your-jwt-secret"
    
    # Use a valid UUID format for the sub claim
    import uuid
    user_id = uuid.uuid4()
    
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),  # Must be a string UUID
        "email": "test@example.com",
        "phone": "",
        "app_metadata": {
            "provider": "email",
            "roles": ["authenticated"]
        },
        "user_metadata": {},
        "roles": ["authenticated"],
        "aud": "authenticated",  # Required by Supabase JWT verification
        "exp": int((now + timedelta(hours=1)).timestamp()),
        "iat": int(now.timestamp()),
        "auth_provider": "email"
    }
    
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture
def mock_db_session():
    """Mock database session for testing."""
    from sqlalchemy.ext.asyncio import AsyncSession
    from unittest.mock import MagicMock
    
    session = AsyncMock(spec=AsyncSession)
    
    # Mock commit and refresh
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    
    # Mock execute to return documents
    async def mock_execute(query):
        result = MagicMock()
        result.scalars = MagicMock()
        result.scalars().all = MagicMock(return_value=[])
        result.scalar_one_or_none = MagicMock(return_value=None)
        return result
    
    session.execute = mock_execute
    
    return session


@pytest.mark.asyncio
async def test_upload_valid_pdf_returns_201(mock_db_session):
    """POST /api/v1/documents/ with valid PDF should return 201."""
    # Create a minimal valid PDF (PDF header + minimal content)
    pdf_content = (
        b"%PDF-1.4\n"
        b"1 0 obj\n"
        b"<< /Type /Catalog /Pages 2 0 R >>\n"
        b"endobj\n"
        b"2 0 obj\n"
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>\n"
        b"endobj\n"
        b"3 0 obj\n"
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\n"
        b"endobj\n"
        b"xref\n"
        b"0 4\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000058 00000 n \n"
        b"0000000115 00000 n \n"
        b"trailer\n"
        b"<< /Size 4 /Root 1 0 R >>\n"
        b"startxref\n"
        b"193\n"
        b"%%EOF\n"
    )
    
    jwt_token = create_test_jwt()
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")}
        headers = {"Authorization": f"Bearer {jwt_token}"}
        response = await client.post("/api/v1/documents/", files=files, headers=headers)
    
    # Debug output
    print(f"Response status: {response.status_code}")
    print(f"Response body: {response.text}")
    
    assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
    data = response.json()
    assert "id" in data
    assert data["filename"] == "test.pdf"
    assert data["status"] == "pending"
    assert data["language"] == "en"


@pytest.mark.asyncio
async def test_upload_non_pdf_returns_400():
    """POST /api/v1/documents/ with non-PDF file should return 400."""
    jwt_token = create_test_jwt()
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("test.txt", io.BytesIO(b"Hello, World!"), "text/plain")}
        headers = {"Authorization": f"Bearer {jwt_token}"}
        response = await client.post("/api/v1/documents/", files=files, headers=headers)
    
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert "PDF" in data["detail"]


@pytest.mark.asyncio
async def test_upload_file_with_wrong_extension_returns_400():
    """POST /api/v1/documents/ with wrong file extension should return 400."""
    pdf_content = b"%PDF-1.4...fake pdf..."
    
    jwt_token = create_test_jwt()
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("document.docx", io.BytesIO(pdf_content), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        headers = {"Authorization": f"Bearer {jwt_token}"}
        response = await client.post("/api/v1/documents/", files=files, headers=headers)
    
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_list_documents_returns_200():
    """GET /api/v1/documents/ should return 200 with authenticated user."""
    jwt_token = create_test_jwt()
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {jwt_token}"}
        response = await client.get("/api/v1/documents/", headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    assert "documents" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_upload_large_file_returns_400():
    """POST /api/v1/documents/ with file > 50MB should return 400."""
    # Create a file larger than 50MB (51 * 1024 * 1024 bytes)
    large_content = b"%" + b"X" * (51 * 1024 * 1024)
    
    jwt_token = create_test_jwt()
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("large.pdf", io.BytesIO(large_content), "application/pdf")}
        headers = {"Authorization": f"Bearer {jwt_token}"}
        response = await client.post("/api/v1/documents/", files=files, headers=headers)
    
    assert response.status_code == 400
    data = response.json()
    assert "50MB" in data["detail"]
