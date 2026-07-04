"""add failed_blocks column to documents table

Revision ID: 0003_failed_blocks_column
Revises: 0002_error_log_column
Create Date: 2026-05-01T13:30:00+01:00
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "0003_failed_blocks_column"
down_revision: Union[str, None] = "0002_error_log_column"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column(
            "failed_blocks",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Count of text blocks that failed extraction",
        ),
    )


def downgrade() -> None:
    op.drop_column("documents", "failed_blocks")
