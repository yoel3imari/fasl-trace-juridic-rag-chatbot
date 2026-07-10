"""
Pipeline service — orchestrates chunking, embedding, and vector storage.
"""

import logging
from uuid import UUID

from app.services.pdf_engine import ExtractionResult
from app.services.chunking_service import chunk_document
from app.services.embedding_service import encode_dense, encode_sparse, warmup
from app.services.vector_store_service import (
    ensure_collection,
    ensure_partition,
    insert_chunks,
)

logger = logging.getLogger(__name__)


def _uuid_to_int64(uuid_value: UUID) -> int:
    """Convert a UUID to a deterministic positive INT64 for Milvus."""
    return abs(hash(str(uuid_value))) & 0x7FFFFFFFFFFFFFFF


async def run_vector_pipeline(
    extraction: ExtractionResult,
    user_id: int,
    document_id: UUID,
) -> str:
    """
    Run the full vector pipeline: chunk -> embed -> upsert.

    Args:
        extraction: Result from pdf_engine.process_document().
        user_id: The user's ID as a deterministic INT64 (for Milvus partition key).
        document_id: The document UUID.

    Returns:
        Status string: ``"vectorized"`` on success.

    Raises:
        RuntimeError: If embedding fails critically.
    """
    # Stage 1: Chunk the extracted text blocks
    chunks = chunk_document(extraction.chunks)
    if not chunks:
        logger.info("No chunks produced for document %s — nothing to vectorize", document_id)
        return "vectorized"

    # Stage 2: Ensure Milvus collection and user partition exist
    ensure_collection()
    ensure_partition(user_id)

    # Stage 3: Embed all chunks (batch dense + sparse)
    chunk_texts = [c.text for c in chunks]
    try:
        dense_vectors = encode_dense(chunk_texts)
        sparse_vectors = encode_sparse(chunk_texts)
    except RuntimeError as e:
        raise RuntimeError(f"Embedding failed: {e}")

    # Stage 4: Prepare Milvus entities
    doc_id_int = _uuid_to_int64(document_id)
    milvus_chunks = []
    for i, (chunk, dense, sparse) in enumerate(zip(chunks, dense_vectors, sparse_vectors)):
        milvus_chunks.append({
            "user_id": user_id,
            "document_id": doc_id_int,
            "chunk_index": chunk.chunk_index,
            "dense_vector": dense,
            "sparse_vector": sparse,
            "text": chunk.text,
            "page_number": chunk.page_number,
            "section_title": chunk.section_title or "",
            "metadata": chunk.metadata,
        })

    # Stage 5: Insert into Milvus
    chunk_ids = insert_chunks(user_id, milvus_chunks)
    logger.info(
        "Vector pipeline complete: %d chunks -> %d Milvus entries for document %s",
        len(chunks),
        len(chunk_ids),
        document_id,
    )

    return "vectorized"


async def warmup_pipeline() -> bool:
    """Pre-load the embedding model (call at server startup).

    Returns:
        True if the model loaded successfully, False otherwise.
    """
    return warmup()
