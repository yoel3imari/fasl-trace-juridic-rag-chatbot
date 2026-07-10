"""
Vector store service — collection management and CRUD for Milvus.

Uses module-level functions with @lru_cache for singleton patterns,
consistent with crypto_service.py.
"""

import functools
import logging
import time
from functools import lru_cache

from pymilvus import (
    AnnSearchRequest,
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    RRFRanker,
    utility,
)

from app.core.config import get_settings
from app.core.milvus_client import ensure_connection, get_milvus_client

logger = logging.getLogger(__name__)

# ── Schema constants ──────────────────────────────────────────────────────

_OUTPUT_FIELDS = [
    "document_id",
    "chunk_index",
    "text",
    "page_number",
    "section_title",
    "metadata",
]


def _build_schema() -> CollectionSchema:
    """Build the collection schema for fasl_trace_chunks."""
    fields = [
        FieldSchema(
            name="id",
            dtype=DataType.INT64,
            is_primary=True,
            auto_id=True,
        ),
        FieldSchema(name="user_id", dtype=DataType.INT64),
        FieldSchema(name="document_id", dtype=DataType.INT64),
        FieldSchema(name="chunk_index", dtype=DataType.INT32),
        FieldSchema(name="dense_vector", dtype=DataType.FLOAT_VECTOR, dim=1024),
        FieldSchema(name="sparse_vector", dtype=DataType.SPARSE_FLOAT_VECTOR),
        FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
        FieldSchema(name="page_number", dtype=DataType.INT32),
        FieldSchema(name="section_title", dtype=DataType.VARCHAR, max_length=512),
        FieldSchema(name="metadata", dtype=DataType.JSON),
    ]
    return CollectionSchema(
        fields,
        description="Fasl Trace legal RAG chunks with dense + sparse vectors",
    )


# ── Retry helper ──────────────────────────────────────────────────────────


def _retry(max_attempts: int = 3, base_delay: float = 1.0):
    """Decorator: retry with exponential backoff, checking connection first."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception: BaseException = RuntimeError("No exception recorded")
            for attempt in range(1, max_attempts + 1):
                try:
                    ensure_connection()
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts:
                        delay = base_delay * (2 ** (attempt - 1))
                        logger.warning(
                            "%s attempt %d/%d failed — retrying in %.1fs: %s",
                            func.__name__,
                            attempt,
                            max_attempts,
                            delay,
                            e,
                        )
                        time.sleep(delay)
            logger.error(
                "%s failed after %d attempts",
                func.__name__,
                max_attempts,
            )
            raise last_exception
        return wrapper
    return decorator


# ── Collection lifecycle ──────────────────────────────────────────────────


@lru_cache
def ensure_collection() -> str:
    """
    Create the fasl_trace_chunks collection with indexes if it doesn't exist.
    Returns the collection name.  Cached via lru_cache — called once.
    """
    get_milvus_client()

    collection_name = get_settings().milvus_collection

    if utility.has_collection(collection_name):
        collection = Collection(collection_name)
        collection.load()
        logger.info("Collection '%s' already exists — loaded", collection_name)
        return collection_name

    schema = _build_schema()
    collection = Collection(name=collection_name, schema=schema)
    logger.info("Created collection '%s'", collection_name)

    # ── Create indexes ────────────────────────────────────────────────
    dense_index = {
        "index_type": "IVF_FLAT",
        "metric_type": "IP",
        "params": {"nlist": 1024},
    }
    collection.create_index("dense_vector", dense_index)
    logger.info("Created dense vector index on '%s'", collection_name)

    sparse_index = {
        "index_type": "SPARSE_INVERTED_INDEX",
        "metric_type": "IP",
    }
    collection.create_index("sparse_vector", sparse_index)
    logger.info("Created sparse vector index on '%s'", collection_name)

    collection.load()
    logger.info("Loaded collection '%s'", collection_name)
    return collection_name


def _get_collection() -> Collection:
    """Return a Collection handle (ensures collection exists first)."""
    name = ensure_collection()
    return Collection(name)


def collection_exists() -> bool:
    """Check if the fasl_trace_chunks collection exists in Milvus."""
    ensure_connection()
    return utility.has_collection(get_settings().milvus_collection)


# ── Partition management ──────────────────────────────────────────────────


def ensure_partition(user_id: int) -> str:
    """
    Create partition ``p_{user_id}`` if it doesn't exist.
    Returns the partition name.
    """
    collection = _get_collection()
    partition_name = f"p_{user_id}"

    if partition_name in collection.partitions:
        return partition_name

    collection.create_partition(partition_name)
    logger.info("Created partition '%s'", partition_name)
    return partition_name


def delete_partition(user_id: int) -> None:
    """
    Drop the entire partition for a user.
    Releases the collection first (required before dropping a partition).
    """
    collection = _get_collection()
    partition_name = f"p_{user_id}"

    if partition_name not in collection.partitions:
        logger.warning("Partition '%s' does not exist — nothing to drop", partition_name)
        return

    collection.release()
    collection.drop_partition(partition_name)
    collection.load()
    logger.info("Dropped partition '%s'", partition_name)


# ── CRUD operations ───────────────────────────────────────────────────────


@_retry()
def insert_chunks(user_id: int, chunks: list[dict]) -> list[int]:
    """
    Insert a batch of chunks into the user's partition.
    Each chunk dict must contain: user_id, document_id, chunk_index,
    dense_vector, sparse_vector, text, page_number, section_title, metadata.
    Returns a list of auto-generated chunk IDs.
    """
    collection = _get_collection()
    partition_name = ensure_partition(user_id)

    entities = [
        [c["user_id"] for c in chunks],
        [c["document_id"] for c in chunks],
        [c["chunk_index"] for c in chunks],
        [c["dense_vector"] for c in chunks],
        [c["sparse_vector"] for c in chunks],
        [c["text"] for c in chunks],
        [c["page_number"] for c in chunks],
        [c["section_title"] for c in chunks],
        [c["metadata"] for c in chunks],
    ]

    mr = collection.insert(entities, partition_name=partition_name)
    collection.flush()
    ids = mr.primary_keys
    logger.info(
        "Inserted %d chunks into partition '%s' (ids: %s...)",
        len(chunks),
        partition_name,
        ids[:3] if len(ids) >= 3 else ids,
    )
    return list(ids)


@_retry()
def delete_document_chunks(user_id: int, document_id: int) -> int:
    """
    Delete all chunks belonging to a document within the user's partition.
    Returns the number of deleted entities.
    """
    collection = _get_collection()
    partition_name = f"p_{user_id}"
    expr = f"document_id == {document_id}"

    mr = collection.delete(expr, partition_name=partition_name)
    collection.flush()
    deleted_count = mr.delete_count
    logger.info(
        "Deleted %d chunks for document_id=%s in partition '%s'",
        deleted_count,
        document_id,
        partition_name,
    )
    return deleted_count


# ── Search operations ─────────────────────────────────────────────────────


def _hit_to_dict(hit, output_fields: list[str]) -> dict:
    """Convert a pymilvus hit to a plain dict."""
    row: dict = {"id": hit.id, "score": hit.distance}

    if hasattr(hit, "fields") and hit.fields is not None:
        for field in output_fields:
            row[field] = hit.fields.get(field)
    elif hasattr(hit, "entity") and hit.entity is not None:
        for field in output_fields:
            row[field] = hit.entity.get(field)
    return row


@_retry()
def hybrid_search(
    user_id: int,
    dense_vec: list[float],
    sparse_vec: dict[int, float],
    query_text: str = "",
    top_k: int = 20,
    filters: str = "",
) -> list[dict]:
    """
    Hybrid search: dense ANN + sparse ANN merged via RRF.
    Always scoped to the user's partition for RLS.
    Returns a list of dicts sorted by combined score.
    """
    collection = _get_collection()
    partition_name = f"p_{user_id}"

    if not collection.is_loaded:
        collection.load()

    dense_params = {
        "metric_type": "IP",
        "params": {"nprobe": 10},
    }
    sparse_params = {
        "metric_type": "IP",
    }

    expr = filters or None

    dense_req = AnnSearchRequest(
        data=[dense_vec],
        anns_field="dense_vector",
        param=dense_params,
        limit=top_k,
        expr=expr,
    )
    sparse_req = AnnSearchRequest(
        data=[sparse_vec],
        anns_field="sparse_vector",
        param=sparse_params,
        limit=top_k,
        expr=expr,
    )

    results = collection.hybrid_search(
        reqs=[dense_req, sparse_req],
        rerank=RRFRanker(k=60),
        limit=top_k,
        output_fields=_OUTPUT_FIELDS,
        partition_names=[partition_name],
    )

    hits = results[0] if results else []
    output = [_hit_to_dict(hit, _OUTPUT_FIELDS) for hit in hits]
    logger.debug(
        "hybrid_search(user_id=%s, top_k=%s) returned %d results",
        user_id,
        top_k,
        len(output),
    )
    return output


@_retry()
def search_dense(
    user_id: int,
    dense_vec: list[float],
    top_k: int = 20,
    filters: str = "",
) -> list[dict]:
    """
    Dense-only ANN search scoped to the user's partition.
    Fallback when sparse vectors aren't available.
    """
    collection = _get_collection()
    partition_name = f"p_{user_id}"

    if not collection.is_loaded:
        collection.load()

    search_params = {
        "metric_type": "IP",
        "params": {"nprobe": 10},
    }

    results = collection.search(
        data=[dense_vec],
        anns_field="dense_vector",
        param=search_params,
        limit=top_k,
        expr=filters or None,
        output_fields=_OUTPUT_FIELDS,
        partition_names=[partition_name],
    )

    hits = results[0] if results else []
    output = [_hit_to_dict(hit, _OUTPUT_FIELDS) for hit in hits]
    logger.debug(
        "search_dense(user_id=%s, top_k=%s) returned %d results",
        user_id,
        top_k,
        len(output),
    )
    return output


@_retry()
def search_sparse(
    user_id: int,
    sparse_vec: dict[int, float],
    top_k: int = 20,
    filters: str = "",
) -> list[dict]:
    """
    Sparse-only ANN search scoped to the user's partition.
    Fallback when dense vectors aren't available.
    """
    collection = _get_collection()
    partition_name = f"p_{user_id}"

    if not collection.is_loaded:
        collection.load()

    search_params = {
        "metric_type": "IP",
    }

    results = collection.search(
        data=[sparse_vec],
        anns_field="sparse_vector",
        param=search_params,
        limit=top_k,
        expr=filters or None,
        output_fields=_OUTPUT_FIELDS,
        partition_names=[partition_name],
    )

    hits = results[0] if results else []
    output = [_hit_to_dict(hit, _OUTPUT_FIELDS) for hit in hits]
    logger.debug(
        "search_sparse(user_id=%s, top_k=%s) returned %d results",
        user_id,
        top_k,
        len(output),
    )
    return output
