"""
Milvus client connection management — singleton via lru_cache.
"""

import logging
from functools import lru_cache

from pymilvus import connections, utility

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_ALIAS = "default"


def _connect() -> None:
    """Establish connection to Milvus using settings."""
    settings = get_settings()
    logger.info(
        "Connecting to Milvus at %s:%s",
        settings.milvus_host,
        settings.milvus_port,
    )
    connections.connect(
        alias=_ALIAS,
        host=settings.milvus_host,
        port=settings.milvus_port,
    )
    logger.info("Connected to Milvus (alias=%s)", _ALIAS)


@lru_cache
def get_milvus_client() -> str:
    """Return the connection alias after establishing connection. Singleton."""
    _connect()
    return _ALIAS


def ensure_connection() -> str:
    """Check connection health and reconnect if dropped. Returns alias."""
    try:
        utility.list_collections()
    except Exception:
        logger.warning("Milvus connection lost — reconnecting...")
        try:
            connections.disconnect(_ALIAS)
        except Exception:
            pass
        get_milvus_client.cache_clear()
        _connect()
    return _ALIAS


def close() -> None:
    """Gracefully close the Milvus connection."""
    try:
        connections.disconnect(_ALIAS)
        logger.info("Disconnected from Milvus")
    except Exception:
        logger.exception("Error disconnecting from Milvus")
    get_milvus_client.cache_clear()
