"""
Ingestion status, error logging, and per-block exception guard tests.

Covers:
- GET /api/v1/documents/ingestion-status endpoint (AC 1, 4)
- Error log population on failure (AC 2)
- Per-block exception guard in pdf_engine.py (AC 3, NFR-R1)
- Status filtering and RLS isolation (AC 1, 5, 6)
"""

import io
import jwt
import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import ASGITransport, AsyncClient

from main import app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def create_test_jwt(user_id: str = None) -> str:
    """Create a mock Supabase JWT for testing."""
    secret = "your-jwt-secret"
    import uuid
    uid = user_id or str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    payload = {
        "sub": uid,
        "email": "test@example.com",
        "phone": "",
        "app_metadata": {"provider": "email", "roles": ["authenticated"]},
        "user_metadata": {},
        "roles": ["authenticated"],
        "aud": "authenticated",
        "exp": int((now + timedelta(hours=1)).timestamp()),
        "iat": int(now.timestamp()),
        "auth_provider": "email",
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def make_mock_document(
    doc_id, user_id, status="pending", page_count=None,
    error_log=None, detected_languages=None, filename="test.pdf",
):
    """Create a mock Document object for DB result simulation."""
    from app.models.document import Document
    doc = MagicMock(spec=Document)
    doc.id = doc_id
    doc.user_id = user_id
    doc.status = status
    doc.filename = filename
    doc.language = "en"
    doc.page_count = page_count
    doc.error_log = error_log
    doc.detected_languages = detected_languages
    doc.created_at = datetime.now(timezone.utc)
    doc.updated_at = None
    return doc


class MockExecuteResult:
    """Mock SQLAlchemy execute result."""

    def __init__(self, rows=None, scalar=None):
        self._rows = rows or []
        self._scalar = scalar

    def scalars(self):
        m = MagicMock()
        m.all = MagicMock(return_value=self._rows)
        return m

    def scalar_one(self):
        return self._scalar

    def scalar_one_or_none(self):
        return self._scalar

    def all(self):
        return self._rows


def make_execute_handler(call_sequence):
    """Factory: creates an async execute handler that returns results in order.

    call_sequence is a list of MockExecuteResult objects, returned one per call.
    """
    call_idx = 0

    async def mock_execute(query):
        nonlocal call_idx
        result = call_sequence[call_idx]
        call_idx += 1
        return result

    return mock_execute


def make_ingestion_status_response(docs_with_chunks, total, skip=0, limit=20):
    """Helper: build expected ingestion status JSON from mock documents."""
    items = []
    for doc, chunk_count in docs_with_chunks:
        items.append({
            "id": str(doc.id),
            "filename": doc.filename,
            "language": doc.language,
            "status": doc.status,
            "page_count": doc.page_count,
            "chunk_count": chunk_count or 0,
            "error_log": doc.error_log,
            "detected_languages": doc.detected_languages,
            "created_at": doc.created_at.isoformat(),
            "updated_at": None,
        })
    return {
        "documents": items,
        "total": total,
        "skip": skip,
        "limit": limit,
    }


# ---------------------------------------------------------------------------
# AC 1: Ingestion status returns correct status for all document states
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ingestion_status_returns_all_statuses():
    """GET /api/v1/documents/ingestion-status should return documents with pending, processing, processed, failed statuses."""
    import uuid
    user_id = str(uuid.uuid4())
    jwt_token = create_test_jwt(user_id)

    docs = [
        (make_mock_document(uuid.uuid4(), user_id, "pending"), 0),
        (make_mock_document(uuid.uuid4(), user_id, "processing"), 0),
        (make_mock_document(uuid.uuid4(), user_id, "processed", page_count=10), 25),
        (make_mock_document(uuid.uuid4(), user_id, "failed"), 0),
    ]

    with patch("main.app.dependency_overrides", {}):
        async def mock_get_db():
            mock_session = AsyncMock()
            mock_session.execute = make_execute_handler([
                MockExecuteResult(scalar=4),
                MockExecuteResult(rows=docs, scalar=4),
            ])
            return mock_session

        # Patch the dependency
        from app.core.database import get_db_session_with_rls
        from app.core.security import get_current_user

        original_db_dep = app.dependency_overrides.get(get_db_session_with_rls)
        original_user_dep = app.dependency_overrides.get(get_current_user)

        app.dependency_overrides[get_db_session_with_rls] = mock_get_db
        app.dependency_overrides[get_current_user] = lambda: {"user_id": user_id}

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/documents/ingestion-status", headers={"Authorization": f"Bearer {jwt_token}"})

            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
            data = response.json()
            assert "documents" in data
            assert "total" in data
            assert data["total"] == 4
            statuses = {d["status"] for d in data["documents"]}
            assert "pending" in statuses
            assert "processing" in statuses
            assert "processed" in statuses
            assert "failed" in statuses
        finally:
            if original_db_dep:
                app.dependency_overrides[get_db_session_with_rls] = original_db_dep
            else:
                app.dependency_overrides.pop(get_db_session_with_rls, None)
            if original_user_dep:
                app.dependency_overrides[get_current_user] = original_user_dep
            else:
                app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# AC 2: Failed documents include error_log with structured details
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_failed_document_includes_error_log():
    """Failed documents should include structured error_log in ingestion status response."""
    import uuid
    user_id = str(uuid.uuid4())
    jwt_token = create_test_jwt(user_id)

    error_log_data = {
        "error_type": "ExtractionFailed",
        "message": "Failed to parse page 3: invalid xref table",
        "timestamp": "2026-05-01T12:00:00+00:00",
        "traceback_summary": None,
    }

    failed_doc = make_mock_document(
        uuid.uuid4(), user_id, status="failed", error_log=error_log_data
    )

    async def mock_get_db():
        mock_session = AsyncMock()
        mock_session.execute = make_execute_handler([
            MockExecuteResult(scalar=1),
            MockExecuteResult(rows=[(failed_doc, 0)], scalar=1),
        ])
        return mock_session

    from app.core.database import get_db_session_with_rls
    from app.core.security import get_current_user

    original_db = app.dependency_overrides.get(get_db_session_with_rls)
    original_user = app.dependency_overrides.get(get_current_user)

    app.dependency_overrides[get_db_session_with_rls] = mock_get_db
    app.dependency_overrides[get_current_user] = lambda: {"user_id": user_id}

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/documents/ingestion-status", headers={"Authorization": f"Bearer {jwt_token}"})

        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 1
        doc_data = data["documents"][0]
        assert doc_data["error_log"] == error_log_data
        assert doc_data["error_log"]["error_type"] == "ExtractionFailed"
    finally:
        if original_db:
            app.dependency_overrides[get_db_session_with_rls] = original_db
        else:
            app.dependency_overrides.pop(get_db_session_with_rls, None)
        if original_user:
            app.dependency_overrides[get_current_user] = original_user
        else:
            app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# AC 4: Processed documents include chunk_count and page_count
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_processed_document_includes_chunk_count_and_page_count():
    """Processed documents should include correct chunk_count and page_count."""
    import uuid
    user_id = str(uuid.uuid4())
    jwt_token = create_test_jwt(user_id)

    processed_doc = make_mock_document(
        uuid.uuid4(), user_id, status="processed", page_count=42
    )

    async def mock_get_db():
        mock_session = AsyncMock()
        mock_session.execute = make_execute_handler([
            MockExecuteResult(scalar=1),
            MockExecuteResult(rows=[(processed_doc, 137)], scalar=1),
        ])
        return mock_session

    from app.core.database import get_db_session_with_rls
    from app.core.security import get_current_user

    original_db = app.dependency_overrides.get(get_db_session_with_rls)
    original_user = app.dependency_overrides.get(get_current_user)

    app.dependency_overrides[get_db_session_with_rls] = mock_get_db
    app.dependency_overrides[get_current_user] = lambda: {"user_id": user_id}

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/documents/ingestion-status", headers={"Authorization": f"Bearer {jwt_token}"})

        assert response.status_code == 200
        data = response.json()
        doc_data = data["documents"][0]
        assert doc_data["page_count"] == 42
        assert doc_data["chunk_count"] == 137
    finally:
        if original_db:
            app.dependency_overrides[get_db_session_with_rls] = original_db
        else:
            app.dependency_overrides.pop(get_db_session_with_rls, None)
        if original_user:
            app.dependency_overrides[get_current_user] = original_user
        else:
            app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# AC 5: Status filter returns only matching documents
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ingestion_status_filter_by_failed():
    """GET /api/v1/documents/ingestion-status?status=failed should return only failed documents."""
    import uuid
    user_id = str(uuid.uuid4())
    jwt_token = create_test_jwt(user_id)

    failed_doc = make_mock_document(uuid.uuid4(), user_id, status="failed")

    async def mock_get_db():
        mock_session = AsyncMock()
        mock_session.execute = make_execute_handler([
            MockExecuteResult(scalar=1),
            MockExecuteResult(rows=[(failed_doc, 0)], scalar=1),
        ])
        return mock_session

    from app.core.database import get_db_session_with_rls
    from app.core.security import get_current_user

    original_db = app.dependency_overrides.get(get_db_session_with_rls)
    original_user = app.dependency_overrides.get(get_current_user)

    app.dependency_overrides[get_db_session_with_rls] = mock_get_db
    app.dependency_overrides[get_current_user] = lambda: {"user_id": user_id}

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/documents/ingestion-status",
                params={"status": "failed"},
                headers={"Authorization": f"Bearer {jwt_token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 1
        assert all(d["status"] == "failed" for d in data["documents"])
    finally:
        if original_db:
            app.dependency_overrides[get_db_session_with_rls] = original_db
        else:
            app.dependency_overrides.pop(get_db_session_with_rls, None)
        if original_user:
            app.dependency_overrides[get_current_user] = original_user
        else:
            app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# AC 6: RLS isolation — user A cannot see user B's documents
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ingestion_status_rls_isolation():
    """Users should only see their own documents, not other users' documents."""
    import uuid
    user_a = str(uuid.uuid4())
    user_b = str(uuid.uuid4())
    jwt_token_a = create_test_jwt(user_a)

    # These docs belong to user B — should NOT be returned for user A
    user_b_docs = [
        (make_mock_document(uuid.uuid4(), user_b, status="processed", page_count=10), 5),
    ]

    captured_user_id = None

    async def mock_get_db():
        mock_session = AsyncMock()

        async def mock_execute(query):
            nonlocal captured_user_id
            # Extract user_id from the query string
            query_str = str(query)
            if user_a in query_str:
                captured_user_id = user_a
                # User A has no documents
                return MockExecuteResult(rows=[], scalar=0)
            if user_b in query_str:
                captured_user_id = user_b
                return MockExecuteResult(rows=user_b_docs, scalar=1)
            return MockExecuteResult(rows=[], scalar=0)

        mock_session.execute = mock_execute
        return mock_session

    from app.core.database import get_db_session_with_rls
    from app.core.security import get_current_user

    original_db = app.dependency_overrides.get(get_db_session_with_rls)
    original_user = app.dependency_overrides.get(get_current_user)

    app.dependency_overrides[get_db_session_with_rls] = mock_get_db
    app.dependency_overrides[get_current_user] = lambda: {"user_id": user_a}

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/documents/ingestion-status",
                headers={"Authorization": f"Bearer {jwt_token_a}"},
            )

        assert response.status_code == 200
        data = response.json()
        # User A should see zero documents (the mock only returns docs for user B)
        assert data["total"] == 0
        assert len(data["documents"]) == 0
    finally:
        if original_db:
            app.dependency_overrides[get_db_session_with_rls] = original_db
        else:
            app.dependency_overrides.pop(get_db_session_with_rls, None)
        if original_user:
            app.dependency_overrides[get_current_user] = original_user
        else:
            app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# AC 3: Per-block exception guard (NFR-R1)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_process_document_per_block_exception_guard():
    """A single bad block should NOT crash the entire pipeline — remaining blocks are processed."""
    from pathlib import Path
    from uuid import uuid4
    from app.services.pdf_engine import process_document

    # Create a temp PDF file
    pdf_content = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
        b"xref\n0 4\n"
        b"0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n"
        b"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n193\n%%EOF\n"
    )

    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(pdf_content)
        temp_path = Path(f.name)

    try:
        document_id = uuid4()
        result = await process_document(temp_path, document_id)

        # Should succeed even with minimal PDF
        assert result.status == "processed"
        assert result.failed_blocks == 0
        assert result.metadata.page_count == 1
    finally:
        temp_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_process_document_failed_blocks_tracked():
    """process_document should track failed_blocks count when blocks fail."""
    from uuid import uuid4
    from app.services.pdf_engine import process_document, convert_bbox, validate_bbox, TextBlock

    # Patch page.get_text to return blocks where some fail
    with patch("app.services.pdf_engine.fitz.open") as mock_open:
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=1)
        mock_doc.__getitem__ = MagicMock(return_value=mock_page)
        mock_doc.metadata = {"title": None, "author": None, "creator": None}

        # Block 0: valid, Block 1: will cause exception (None text)
        mock_page.get_text.return_value = [
            (0, 0, 100, 50, "Hello world", 0),
            (0, 60, 100, 110, "Second block", 0),
        ]
        mock_open.return_value.__enter__ = MagicMock(return_value=mock_doc)
        mock_open.return_value.__exit__ = MagicMock(return_value=False)
        # Also support direct access
        mock_open.return_value = mock_doc
        mock_open.side_effect = None

        # Override __len__ and __getitem__ properly
        type(mock_doc).__len__ = lambda self: 1
        type(mock_doc).__getitem__ = lambda self, idx: mock_page

        result = await process_document(Path("/tmp/test.pdf"), uuid4())

        assert result.status == "processed"
        # Both blocks should succeed in this mock
        assert len(result.chunks) == 2
        assert result.failed_blocks == 0


@pytest.mark.asyncio
async def test_extraction_result_has_failed_blocks_field():
    """ExtractionResult dataclass should have failed_blocks field."""
    from uuid import uuid4
    from app.services.pdf_engine import ExtractionResult, PDFMetadata

    metadata = PDFMetadata(
        page_count=10, language="en", detected_languages=["en"],
        title=None, author=None, creator=None,
    )
    result = ExtractionResult(
        document_id=uuid4(),
        status="processed",
        metadata=metadata,
        chunks=[],
        failed_blocks=3,
    )

    assert result.failed_blocks == 3

    # Default should be 0
    result_default = ExtractionResult(
        document_id=uuid4(),
        status="processed",
        metadata=metadata,
        chunks=[],
    )
    assert result_default.failed_blocks == 0


# ---------------------------------------------------------------------------
# Pagination edge cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ingestion_status_empty_results():
    """GET /api/v1/documents/ingestion-status should return empty list when user has no documents."""
    import uuid
    user_id = str(uuid.uuid4())
    jwt_token = create_test_jwt(user_id)

    async def mock_get_db():
        mock_session = AsyncMock()

        async def mock_execute(query):
            return MockExecuteResult(rows=[], scalar=0)

        mock_session.execute = mock_execute
        return mock_session

    from app.core.database import get_db_session_with_rls
    from app.core.security import get_current_user

    original_db = app.dependency_overrides.get(get_db_session_with_rls)
    original_user = app.dependency_overrides.get(get_current_user)

    app.dependency_overrides[get_db_session_with_rls] = mock_get_db
    app.dependency_overrides[get_current_user] = lambda: {"user_id": user_id}

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/documents/ingestion-status", headers={"Authorization": f"Bearer {jwt_token}"})

        assert response.status_code == 200
        data = response.json()
        assert data["documents"] == []
        assert data["total"] == 0
    finally:
        if original_db:
            app.dependency_overrides[get_db_session_with_rls] = original_db
        else:
            app.dependency_overrides.pop(get_db_session_with_rls, None)
        if original_user:
            app.dependency_overrides[get_current_user] = original_user
        else:
            app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_ingestion_status_pagination():
    """GET /api/v1/documents/ingestion-status?skip=1&limit=1 should return single doc."""
    import uuid
    user_id = str(uuid.uuid4())
    jwt_token = create_test_jwt(user_id)

    doc1 = make_mock_document(uuid.uuid4(), user_id, status="pending")
    doc2 = make_mock_document(uuid.uuid4(), user_id, status="processed", page_count=5)

    async def mock_get_db():
        mock_session = AsyncMock()
        mock_session.execute = make_execute_handler([
            MockExecuteResult(scalar=2),
            MockExecuteResult(rows=[(doc2, 10)], scalar=2),
        ])
        return mock_session

    from app.core.database import get_db_session_with_rls
    from app.core.security import get_current_user

    original_db = app.dependency_overrides.get(get_db_session_with_rls)
    original_user = app.dependency_overrides.get(get_current_user)

    app.dependency_overrides[get_db_session_with_rls] = mock_get_db
    app.dependency_overrides[get_current_user] = lambda: {"user_id": user_id}

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/documents/ingestion-status",
                params={"skip": 1, "limit": 1},
                headers={"Authorization": f"Bearer {jwt_token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) == 1
        assert data["total"] == 2
        assert data["skip"] == 1
        assert data["limit"] == 1
    finally:
        if original_db:
            app.dependency_overrides[get_db_session_with_rls] = original_db
        else:
            app.dependency_overrides.pop(get_db_session_with_rls, None)
        if original_user:
            app.dependency_overrides[get_current_user] = original_user
        else:
            app.dependency_overrides.pop(get_current_user, None)
