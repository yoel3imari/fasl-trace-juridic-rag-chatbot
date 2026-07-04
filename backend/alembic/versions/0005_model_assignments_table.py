"""Create model_assignments table

Revision ID: 0005_model_assignments_table
Revises: 0004_llm_providers_table
Create Date: 2026-05-02
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_model_assignments_table"
down_revision = "0004_llm_providers_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_assignments",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("provider_id", sa.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("model_name", sa.String(255), nullable=False),
        sa.Column("system_function", sa.String(50), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("health_status", sa.String(50), nullable=True),
        sa.Column("health_message", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()"), onupdate=sa.text("now()")),
    )

    # FK to llm_providers
    op.create_foreign_key(
        "fk_model_assignments_provider_id",
        "model_assignments",
        "llm_providers",
        ["provider_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    # Partial unique index: only one active assignment per (user_id, system_function)
    op.create_index(
        "uq_model_assignments_active_per_function",
        "model_assignments",
        ["user_id", "system_function"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )

    # Composite index for common query pattern
    op.create_index(
        "idx_model_assignments_user_function_active",
        "model_assignments",
        ["user_id", "system_function", "is_active"],
        unique=False,
    )

    op.execute("""
        ALTER TABLE model_assignments ENABLE ROW LEVEL SECURITY;
    """)
    op.execute("""
        CREATE POLICY model_assignments_user_policy ON model_assignments
        USING (user_id = (current_setting('request.jwt.claims', true)::jsonb->>'sub')::uuid)
        WITH CHECK (user_id = (current_setting('request.jwt.claims', true)::jsonb->>'sub')::uuid);
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS model_assignments_user_policy ON model_assignments;")
    op.execute("ALTER TABLE model_assignments DISABLE ROW LEVEL SECURITY;")
    op.drop_index("idx_model_assignments_user_function_active", table_name="model_assignments")
    op.drop_index("uq_model_assignments_active_per_function", table_name="model_assignments")
    op.drop_constraint("fk_model_assignments_provider_id", "model_assignments", type_="foreignkey")
    op.drop_table("model_assignments")
