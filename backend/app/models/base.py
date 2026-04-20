"""
SQLAlchemy base model — all domain models inherit from this.

Uses UUID primary keys (required for Supabase RLS and distributed systems)
and common audit columns (created_at, updated_at, user_id).
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for all SQLAlchemy models."""

    pass


class BaseModel(Base):
    """
    Abstract base providing common columns for all tenant-scoped tables.

    - id: UUID primary key (server-default)
    - user_id: UUID foreign key to Supabase auth.users (RLS enforcement point)
    - created_at: timestamp with timezone (server-default)
    - updated_at: timestamp with timezone (auto-update on modification)
    """

    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
