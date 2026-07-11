"""Create initial schema: documents, document_chunks, collections, document_collections

Revision ID: 0000_initial_schema
Revises: None
Create Date: 2026-05-01T10:00:00+01:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0000_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -------------------------------------------------------------------
    # documents
    # -------------------------------------------------------------------
    op.create_table(
        "documents",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("language", sa.String(10), nullable=False,
                  comment="ISO language code: en, fr, ar"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending",
                  comment="pending | processing | processed | failed"),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("detected_language", sa.String(10), nullable=True),
    )

    # -------------------------------------------------------------------
    # document_chunks
    # -------------------------------------------------------------------
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("document_id", sa.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("bounding_box", postgresql.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
    )

    # -------------------------------------------------------------------
    # collections
    # -------------------------------------------------------------------
    op.create_table(
        "collections",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("name", sa.String(255), nullable=False),
    )

    # -------------------------------------------------------------------
    # document_collections — many-to-many junction
    # -------------------------------------------------------------------
    op.create_table(
        "document_collections",
        sa.Column("document_id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("collection_id", sa.UUID(as_uuid=True), primary_key=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["collection_id"], ["collections.id"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    op.drop_table("document_collections")
    op.drop_table("collections")
    op.drop_table("document_chunks")
    op.drop_table("documents")
