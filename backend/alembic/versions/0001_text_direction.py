"""add text_direction and detected_languages columns

Revision ID: 0001_text_direction
Revises: None
Create Date: 2026-05-01T12:00:00+01:00
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0001_text_direction"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "document_chunks",
        sa.Column(
            "text_direction",
            sa.String(10),
            nullable=False,
            server_default="ltr",
            comment="rtl | ltr | mixed",
        ),
    )
    op.add_column(
        "documents",
        sa.Column(
            "detected_languages",
            postgresql.JSON(),
            nullable=True,
            comment="ISO 639-1 language codes detected in document (e.g. [\"ar\", \"en\"])",
        ),
    )


def downgrade() -> None:
    op.drop_column("document_chunks", "text_direction")
    op.drop_column("documents", "detected_languages")
