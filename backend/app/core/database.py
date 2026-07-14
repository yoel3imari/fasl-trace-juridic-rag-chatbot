"""
Database module — singleton engine and session factory.
This module ensures the database engine is created only once to avoid
connection exhaustion and performance issues.
"""

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from alembic.config import Config
from alembic.runtime.environment import EnvironmentContext
from alembic.script import ScriptDirectory
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.sql import text

from fastapi import Depends

from app.core.config import get_settings
from app.core.security import get_current_user
from app.models.base import Base

logger = logging.getLogger(__name__)

# alembic.ini lives at the backend root: database.py -> app/core -> backend
ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


class Database:
    """
    Singleton database manager.

    Ensures exactly one engine instance exists for the application lifecycle,
    providing proper connection pooling and preventing connection exhaustion.
    """

    _instance: "Database | None" = None
    _engine = None
    _session_factory = None

    @classmethod
    def get_instance(cls) -> "Database":
        """Get or create the singleton database instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        if self._instance is not None:
            raise RuntimeError("Database is a singleton. Use Database.get_instance().")

        settings = get_settings()

        # Create engine once - this provides connection pooling
        self._engine = create_async_engine(
            settings.database_url,
            pool_size=10,  # Maximum connections in pool
            max_overflow=20,  # Extra connections when pool is exhausted
            pool_pre_ping=True,  # Validate connections before use
            pool_recycle=3600,  # Recycle connections after 1 hour
            echo=settings.debug,
        )

        # Session factory for creating new sessions
        self._session_factory = async_sessionmaker(
            bind=self._engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )

        # Add connection event listener for debugging
        if settings.debug:

            @event.listens_for(self._engine.sync_engine, "connect")
            def on_connect(dbapi_conn, conn_record):
                print("[DB] Connection opened")

            @event.listens_for(self._engine.sync_engine, "close")
            def on_close(dbapi_conn, conn_record):
                print("[DB] Connection closed")

    @property
    def engine(self):
        """Get the database engine."""
        if self._engine is None:
            raise RuntimeError("Engine not initialized. Check lifespan startup.")
        return self._engine

    @property
    def session_factory(self):
        """Get the session factory."""
        if self._session_factory is None:
            raise RuntimeError(
                "Session factory not initialized. Check lifespan startup."
            )
        return self._session_factory

    async def close(self):
        """Close all connections in the pool."""
        if self._engine:
            await self._engine.dispose()


# Module-level singleton
db = Database()


async def _set_rls_context(session: AsyncSession, current_user: dict):
    """
    Set the RLS context for the current session.

    For Supabase RLS to work, we need to inject the authenticated user's ID
    into the PostgreSQL session using SET LOCAL. This allows auth.uid() to
    return the correct value for RLS policy evaluation.

    In local dev without Supabase RLS roles, the SET LOCAL calls are
    gracefully ignored to avoid crashing on non-Supabase databases.
    """
    user_id = current_user.get("user_id")
    if not user_id:
        return

    # Use a savepoint so SET LOCAL failures don't abort the transaction
    for stmt in [
        f"SET LOCAL jwt.claims = '{json.dumps({'sub': user_id})}'",
        "SET LOCAL role = authenticated",
    ]:
        await session.execute(text("SAVEPOINT rls_try"))
        try:
            await session.execute(text(stmt))
            await session.execute(text("RELEASE SAVEPOINT rls_try"))
        except Exception:
            # Local dev — RLS roles probably don't exist
            await session.execute(text("ROLLBACK TO SAVEPOINT rls_try"))


async def get_db_session_with_rls(
    current_user: dict = Depends(get_current_user),
) -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for database sessions with RLS context.

    Yields a new async session from the singleton engine's session factory.
    Automatically sets RLS context using SET LOCAL jwt.claims.
    Automatically closes the session when the request completes.

    RLS is enforced at the database level via PostgreSQL Row-Level Security
    policies that use auth.uid() to verify the authenticated user.

    Usage:
        @app.get("/items/")
        async def get_items(
            db: AsyncSession = Depends(get_db_session_with_rls),
        ):
            ...
    """
    session = db.session_factory()
    try:
        # Inject RLS context
        await _set_rls_context(session, current_user)
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def get_db_session_service() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for database sessions WITHOUT RLS context.

    Bypasses row-level security so admin-only operations can read/write
    shared resources (e.g. system documents in the official corpus). MUST
    only be wired to endpoints guarded by ``require_admin`` — never expose
    this to ordinary authenticated users.
    """
    session = db.session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def startup_db(app):
    """Startup handler for database connection pool."""
    # The engine is already created at module import time
    # This can be used for additional initialization if needed
    if app.state.settings.debug:
        print("[DB] Database engine ready")


async def shutdown_db(app):
    """Shutdown handler for database connection pool."""
    await db.close()
    if app.state.settings.debug:
        print("[DB] Database engine closed")


async def run_migrations_upgrade() -> None:
    """Apply all pending Alembic migrations at startup.

    Runs ``alembic upgrade head`` against the application engine inside the
    running event loop, guaranteeing the schema is current before any request
    is served. Idempotent — safe to call on every boot.
    """
    settings = get_settings()
    alembic_cfg = Config(str(ALEMBIC_INI))
    alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)
    script = ScriptDirectory.from_config(alembic_cfg)

    logger.info("[DB] Applying database migrations (upgrade head)...")

    # Lazily import models so Base.metadata is fully populated and to avoid
    # any import-time circular dependency on database.py.
    from app.models.document import Document  # noqa: F401
    from app.models.collection import Collection, document_collections  # noqa: F401
    from app.models.chunk import DocumentChunk  # noqa: F401
    from app.models.llm_provider import LLMProvider  # noqa: F401
    from app.models.model_assignment import ModelAssignment  # noqa: F401

    def _do_upgrade(sync_connection):
        env = EnvironmentContext(alembic_cfg, script)
        env.configure(
            connection=sync_connection,
            target_metadata=Base.metadata,
            fn=lambda rev, ctx: script._upgrade_revs("head", rev),
        )
        with env.begin_transaction():
            env.run_migrations()

    async with db.engine.connect() as connection:
        await connection.run_sync(_do_upgrade)

    logger.info("[DB] Schema migrated to head")
