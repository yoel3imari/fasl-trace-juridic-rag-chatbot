"""
Database module — singleton engine and session factory.
This module ensures the database engine is created only once to avoid
connection exhaustion and performance issues.
"""

import json
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.sql import text

from fastapi import Depends

from app.core.config import get_settings, Settings
from app.core.security import get_current_user


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
            pool_size=10,          # Maximum connections in pool
            max_overflow=20,       # Extra connections when pool is exhausted
            pool_pre_ping=True,    # Validate connections before use
            pool_recycle=3600,     # Recycle connections after 1 hour
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
                print(f"[DB] Connection opened")

            @event.listens_for(self._engine.sync_engine, "close")
            def on_close(dbapi_conn, conn_record):
                print(f"[DB] Connection closed")

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
            raise RuntimeError("Session factory not initialized. Check lifespan startup.")
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
    """
    user_id = current_user.get("user_id")
    if user_id:
        # Set the jwt.claims to enable RLS auth.uid() to work
        await session.execute(
            text(f"SET LOCAL jwt.claims = '{json.dumps({'sub': user_id})}'")
        )
        # Also set the role to authenticated for Supabase RLS
        await session.execute(text("SET LOCAL role = authenticated"))


@asynccontextmanager
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
