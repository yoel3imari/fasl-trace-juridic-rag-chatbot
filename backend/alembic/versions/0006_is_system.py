"""add is_system column to documents table

Revision ID: 0006_is_system
Revises: 0005_model_assignments_table
Create Date: 2026-07-11T12:00:00+01:00
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "0006_is_system"
down_revision: Union[str, None] = "0005_model_assignments_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column(
            "is_system",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="True for official corpus documents stored in the shared p_system Milvus partition",
        ),
    )
    op.create_index("ix_documents_is_system", "documents", ["is_system"])


def downgrade() -> None:
    op.drop_index("ix_documents_is_system", table_name="documents")
    op.drop_column("documents", "is_system")
