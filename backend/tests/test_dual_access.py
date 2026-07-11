"""
Dual-access model tests (Pattern A): shared p_system partition + per-user
partitions. These are unit tests that mock Milvus/DB boundaries so they run
without a live vector store.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import vector_store_service as vss
from app.services import pipeline_service as ps
from app.core.security import require_admin
from app.core.config import Settings


# ── partition helpers ────────────────────────────────────────────────────────


def test_user_partition_name_format():
    assert ps.user_partition_name(123) == "p_123"


def test_system_partition_constant():
    assert vss.SYSTEM_PARTITION == "p_system"


@pytest.mark.parametrize(
    "user_id_int,expected",
    [
        (None, ["p_system"]),
        (0, ["p_system", "p_0"]),
        (42, ["p_system", "p_42"]),
    ],
)
def test_get_search_partitions(user_id_int, expected):
    assert vss.get_search_partitions(user_id_int) == expected


# ── pipeline routing ─────────────────────────────────────────────────────────


class _FakeChunk:
    def __init__(self, text, chunk_index=0, page_number=1, section_title=None, metadata=None):
        self.text = text
        self.chunk_index = chunk_index
        self.page_number = page_number
        self.section_title = section_title
        self.metadata = metadata or {}


class _FakeExtraction:
    def __init__(self, chunks):
        self.chunks = chunks
        self.status = "ok"


def _build_extraction(n=2):
    return _FakeExtraction([_FakeChunk(f"text {i}", chunk_index=i) for i in range(n)])


@pytest.mark.asyncio
async def test_run_vector_pipeline_routes_to_user_partition():
    doc_id = uuid.uuid4()
    captured = {}

    with patch.object(ps, "chunk_document", return_value=_build_extraction().chunks), \
         patch.object(ps, "ensure_collection", new=MagicMock()), \
         patch.object(ps, "ensure_partition", new=MagicMock()), \
         patch.object(ps, "encode_dense", new=MagicMock(return_value=[[0.1] * 4 for _ in range(2)])), \
         patch.object(ps, "encode_sparse", new=MagicMock(return_value=[{1: 0.5} for _ in range(2)])), \
         patch.object(ps, "insert_chunks", new=MagicMock(side_effect=lambda p, c: captured.setdefault("partition", p) or [1] * len(c))):
        status = await ps.run_vector_pipeline(
            extraction=_build_extraction(),
            user_id_int=99,
            document_id=doc_id,
            is_system=False,
        )

    assert status == "vectorized"
    assert captured["partition"] == ps.user_partition_name(99)


@pytest.mark.asyncio
async def test_run_vector_pipeline_routes_to_system_partition():
    doc_id = uuid.uuid4()
    captured = {}

    with patch.object(ps, "chunk_document", return_value=_build_extraction().chunks), \
         patch.object(ps, "ensure_collection", new=MagicMock()), \
         patch.object(ps, "ensure_partition", new=MagicMock()), \
         patch.object(ps, "encode_dense", new=MagicMock(return_value=[[0.1] * 4 for _ in range(2)])), \
         patch.object(ps, "encode_sparse", new=MagicMock(return_value=[{1: 0.5} for _ in range(2)])), \
         patch.object(ps, "insert_chunks", new=MagicMock(side_effect=lambda p, c: captured.setdefault("partition", p) or [1] * len(c))):
        status = await ps.run_vector_pipeline(
            extraction=_build_extraction(),
            user_id_int=None,
            document_id=doc_id,
            is_system=True,
        )

    assert status == "vectorized"
    assert captured["partition"] == vss.SYSTEM_PARTITION


@pytest.mark.asyncio
async def test_run_vector_pipeline_system_scopes_chunks():
    doc_id = uuid.uuid4()
    inserted = {}

    with patch.object(ps, "chunk_document", return_value=_build_extraction().chunks), \
         patch.object(ps, "ensure_collection", new=MagicMock()), \
         patch.object(ps, "ensure_partition", new=MagicMock()), \
         patch.object(ps, "encode_dense", new=MagicMock(return_value=[[0.1] * 4 for _ in range(2)])), \
         patch.object(ps, "encode_sparse", new=MagicMock(return_value=[{1: 0.5} for _ in range(2)])), \
         patch.object(ps, "insert_chunks", new=MagicMock(side_effect=lambda p, c: inserted.setdefault("chunks", c))):
        await ps.run_vector_pipeline(
            extraction=_build_extraction(),
            user_id_int=7,
            document_id=doc_id,
            is_system=True,
        )

    assert all(c["scope"] == "system" for c in inserted["chunks"])
    assert all(c["user_id"] == 0 for c in inserted["chunks"])


@pytest.mark.asyncio
async def test_run_vector_pipeline_user_scopes_chunks():
    doc_id = uuid.uuid4()
    inserted = {}

    with patch.object(ps, "chunk_document", return_value=_build_extraction().chunks), \
         patch.object(ps, "ensure_collection", new=MagicMock()), \
         patch.object(ps, "ensure_partition", new=MagicMock()), \
         patch.object(ps, "encode_dense", new=MagicMock(return_value=[[0.1] * 4 for _ in range(2)])), \
         patch.object(ps, "encode_sparse", new=MagicMock(return_value=[{1: 0.5} for _ in range(2)])), \
         patch.object(ps, "insert_chunks", new=MagicMock(side_effect=lambda p, c: inserted.setdefault("chunks", c))):
        await ps.run_vector_pipeline(
            extraction=_build_extraction(),
            user_id_int=7,
            document_id=doc_id,
            is_system=False,
        )

    assert all(c["scope"] == "user" for c in inserted["chunks"])
    assert all(c["user_id"] == 7 for c in inserted["chunks"])


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_run_vector_pipeline_rejects_system_without_user_id():
    with patch.object(ps, "chunk_document", return_value=_build_extraction().chunks), \
         patch.object(ps, "ensure_collection", new=MagicMock()), \
         patch.object(ps, "ensure_partition", new=MagicMock()):
        with pytest.raises(ValueError):
            await ps.run_vector_pipeline(
                extraction=_build_extraction(),
                user_id_int=None,
                document_id=uuid.uuid4(),
                is_system=False,
            )


# ── admin authorization ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_require_admin_allows_app_metadata_role():
    user = {"user_id": str(uuid.uuid4()), "payload": {"app_metadata": {"role": "admin"}}}
    assert await require_admin(current_user=user, settings=Settings()) is user


@pytest.mark.asyncio
async def test_require_admin_allows_top_level_role():
    user = {"user_id": str(uuid.uuid4()), "payload": {"role": "admin"}}
    assert await require_admin(current_user=user, settings=Settings()) is user


@pytest.mark.asyncio
async def test_require_admin_allows_id_allowlist():
    uid = str(uuid.uuid4())
    user = {"user_id": uid, "payload": {}}
    settings = Settings(admin_user_ids=f"other,{uid}")
    assert await require_admin(current_user=user, settings=settings) is user


@pytest.mark.asyncio
async def test_require_admin_rejects_non_admin():
    user = {"user_id": str(uuid.uuid4()), "payload": {"app_metadata": {"role": "authenticated"}}}
    with pytest.raises(Exception):  # HTTPException 403
        await require_admin(current_user=user, settings=Settings())
