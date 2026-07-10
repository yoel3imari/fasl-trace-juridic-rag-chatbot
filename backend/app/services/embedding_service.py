"""
Embedding service — wraps BGE-M3 (BAAI/bge-m3) for dense and sparse vector generation.
"""

import logging
from functools import lru_cache
from types import SimpleNamespace

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_model = None


def _get_model():
    """Lazy-load the BGE-M3 model on first call."""
    global _model
    if _model is not None:
        return _model

    settings = get_settings()
    try:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(
            settings.embedding_model_name,
            device="cpu",
        )
        logger.info("Loaded embedding model: %s", settings.embedding_model_name)
        return _model
    except ImportError:
        raise RuntimeError(
            "sentence_transformers is not installed. "
            "Install it with: pip install sentence-transformers"
        )
    except Exception as e:
        logger.error("Failed to load embedding model: %s", e)
        raise RuntimeError(f"Failed to load embedding model: {e}")


def warmup() -> bool:
    """Pre-load the embedding model. Returns True on success, False on failure."""
    try:
        _get_model()
        return True
    except Exception:
        logger.exception("Embedding model warmup failed")
        return False


def encode_dense(texts: list[str]) -> list[list[float]]:
    """Generate dense embeddings (1024-dim, L2-normalized).

    Args:
        texts: List of input strings to embed.

    Returns:
        List of dense embedding vectors, each a list of 1024 floats.
    """
    model = _get_model()
    settings = get_settings()
    embeddings = model.encode(
        texts,
        normalize_embeddings=True,
        batch_size=settings.embedding_batch_size,
    )
    return embeddings.tolist()


def encode_sparse(texts: list[str]) -> list[dict[int, float]]:
    """Generate sparse token-weight vectors.

    BGE-M3 returns token-level weights compatible with Milvus SparseFloatVector format.

    Args:
        texts: List of input strings to embed.

    Returns:
        List of sparse vectors, each a dict mapping token ID (int) to weight (float).
    """
    model = _get_model()
    settings = get_settings()
    result = model.encode(
        texts,
        output_value="token_weights",
        batch_size=settings.embedding_batch_size,
    )
    return result


def encode_query(text: str) -> tuple[list[float], dict[int, float]]:
    """Encode a single query into both dense and sparse vectors.

    Args:
        text: A single query string.

    Returns:
        Tuple of (dense_vector, sparse_vector).
    """
    dense = encode_dense([text])[0]
    sparse = encode_sparse([text])[0]
    return dense, sparse


@lru_cache
def get_embedding_service() -> SimpleNamespace:
    """Singleton factory for the embedding service.

    Returns a namespace with encode_dense, encode_sparse, encode_query,
    and warmup methods for convenient access. Module-level functions
    can also be imported and used directly.
    """
    return SimpleNamespace(
        encode_dense=encode_dense,
        encode_sparse=encode_sparse,
        encode_query=encode_query,
        warmup=warmup,
    )
