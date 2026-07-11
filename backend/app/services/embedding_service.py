"""
Embedding service — wraps BGE-M3 (via CrispEmbed native ggml) for dense and
sparse vector generation.

CrispEmbed is built from source into the Docker image
(PYTHONPATH=/opt/CrispEmbed/python, LD_LIBRARY_PATH=/opt/CrispEmbed/build) and
exposes a ctypes FFI wrapper. The model is referenced by its registry
short-name (e.g. ``bge-m3``), which auto-downloads the matching GGUF from
HuggingFace on first load.
"""

import importlib
import logging
from functools import lru_cache
from types import SimpleNamespace

import numpy as np

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_model = None


def _get_model():
    """Lazy-load the CrispEmbed model on first call."""
    global _model
    if _model is not None:
        return _model

    settings = get_settings()
    try:
        crispembed = importlib.import_module("crispembed")
        CrispEmbed = crispembed.CrispEmbed
    except ImportError as exc:
        raise RuntimeError(
            "crispembed is not installed. It is built from source into the "
            "Docker image (PYTHONPATH=/opt/CrispEmbed/python, "
            "LD_LIBRARY_PATH=/opt/CrispEmbed/build)."
        ) from exc

    try:
        _model = CrispEmbed(settings.embedding_model_name)
        if not _model.has_sparse:
            logger.warning(
                "Model %s has no sparse head; sparse vectors will be empty.",
                settings.embedding_model_name,
            )
        logger.info("Loaded embedding model: %s", settings.embedding_model_name)
        return _model
    except Exception as e:
        logger.error("Failed to load embedding model: %s", e)
        raise RuntimeError(f"Failed to load embedding model: {e}") from e


def _l2_normalize_rows(embeddings: np.ndarray) -> np.ndarray:
    """L2-normalize each row to unit length (BGE-M3 dense contract).

    CrispEmbed already L2-normalizes dense vectors by default, but we enforce
    the contract here so callers always receive unit-length vectors.
    """
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    # Avoid division by zero for degenerate (all-zero) rows.
    norms[norms == 0.0] = 1.0
    return embeddings / norms


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
    embeddings = model.encode(texts, normalize=True)
    if embeddings.ndim == 1:
        embeddings = embeddings.reshape(1, -1)
    normalized = _l2_normalize_rows(np.asarray(embeddings, dtype=np.float32))
    return normalized.tolist()


def encode_sparse(texts: list[str]) -> list[dict[int, float]]:
    """Generate sparse token-weight vectors.

    BGE-M3 returns token-level weights compatible with Milvus SparseFloatVector
    format (a dict mapping token ID -> weight).

    Args:
        texts: List of input strings to embed.

    Returns:
        List of sparse vectors, each a dict mapping token ID (int) to weight (float).
    """
    model = _get_model()
    return [model.encode_sparse(text) for text in texts]


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
