"""add error_log column to documents table

Revision ID: 0002_error_log_column
Revises: 0001_text_direction
Create Date: 2026-05-01T12:00:00+01:00
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0002_error_log_column"
down_revision: Union[str, None] = "0001_text_direction"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column(
            "error_log",
            postgresql.JSON(),
            nullable=True,
            comment="Structured error log for failed processing",
        ),
    )


def downgrade() -> None:
    op.drop_column("documents", "error_log")
