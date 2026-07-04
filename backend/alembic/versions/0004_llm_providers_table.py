"""Create llm_providers table

Revision ID: 0004_llm_providers_table
Revises: 0003_failed_blocks_column
Create Date: 2026-05-01
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_llm_providers_table"
down_revision = "0003_failed_blocks_column"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "llm_providers",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("provider_type", sa.String(50), nullable=False),
        sa.Column("base_url", sa.String(512), nullable=True),
        sa.Column("api_version", sa.String(50), nullable=True),
        sa.Column("encrypted_api_key", sa.Text(), nullable=True,
            comment="AES-256-GCM encrypted API key; never returned to client"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()"), onupdate=sa.text("now()")),
    )
    op.create_index("idx_llm_providers_user_id", "llm_providers", ["user_id"], unique=False)
    op.create_index("idx_llm_providers_type_active", "llm_providers", ["provider_type", "is_active"], unique=False)

    op.execute("""
        ALTER TABLE llm_providers ENABLE ROW LEVEL SECURITY;
    """)
    op.execute("""
        CREATE POLICY llm_providers_user_policy ON llm_providers
        USING (user_id = (current_setting('request.jwt.claims', true)::jsonb->>'sub')::uuid)
        WITH CHECK (user_id = (current_setting('request.jwt.claims', true)::jsonb->>'sub')::uuid);
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS llm_providers_user_policy ON llm_providers;")
    op.execute("ALTER TABLE llm_providers DISABLE ROW LEVEL SECURITY;")
    op.drop_column("llm_providers", "encrypted_api_key")
    op.drop_table("llm_providers")
