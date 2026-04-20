"""
Collection model — organizes documents into named queryable scopes.
Includes the many-to-many junction table document_collections.
"""

import uuid

from sqlalchemy import Column, ForeignKey, String, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BaseModel

# ---------------------------------------------------------------------------
# Junction table — many-to-many: documents <-> collections
# ---------------------------------------------------------------------------
document_collections = Table(
    "document_collections",
    Base.metadata,
    Column(
        "document_id",
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "collection_id",
        UUID(as_uuid=True),
        ForeignKey("collections.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Collection(BaseModel):
    """
    A named scope/collection that groups documents for targeted querying.

    Table: collections (plural snake_case per naming convention)
    """

    __tablename__ = "collections"

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Relationship — documents in this collection
    documents = relationship(
        "Document",
        secondary=document_collections,
        backref="collections",
        lazy="selectin",
    )
