"""initial schema

Revision ID: 20260917_01
Revises:
Create Date: 2026-09-17
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260917_01"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "consulta_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'PENDING'"), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("total >= 0", name="ck_consulta_jobs_total_nonnegative"),
        sa.CheckConstraint("status IN ('PENDING', 'RUNNING', 'COMPLETED')", name="ck_consulta_jobs_status"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "consulta_cnpjs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cnpj", sa.String(length=14), nullable=False),
        sa.Column("input_order", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'PENDING'"), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("razao_social", sa.String(length=255), nullable=True),
        sa.Column("telefone", sa.String(length=32), nullable=True),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("char_length(cnpj) = 14 AND cnpj ~ '^[0-9]{14}$'", name="ck_consulta_cnpjs_cnpj_digits"),
        sa.CheckConstraint("input_order >= 0", name="ck_consulta_cnpjs_input_order_nonnegative"),
        sa.CheckConstraint("attempt_count >= 0", name="ck_consulta_cnpjs_attempt_count_nonnegative"),
        sa.CheckConstraint("status IN ('PENDING', 'PROCESSING', 'SUCCESS', 'NOT_FOUND', 'FAILED')", name="ck_consulta_cnpjs_status"),
        sa.ForeignKeyConstraint(["job_id"], ["consulta_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "cnpj", name="uq_consulta_cnpjs_job_cnpj"),
        sa.UniqueConstraint("job_id", "input_order", name="uq_consulta_cnpjs_job_input_order"),
    )
    op.create_index("ix_consulta_cnpjs_job_id", "consulta_cnpjs", ["job_id"])
    op.create_index("ix_consulta_cnpjs_queue", "consulta_cnpjs", ["status", "next_attempt_at", "created_at"])
    op.create_table(
        "external_api_control",
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("next_request_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("blocked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("provider"),
    )
    op.bulk_insert(
        sa.table("external_api_control", sa.column("provider", sa.String)),
        [{"provider": "cnpjws_public"}],
    )


def downgrade() -> None:
    op.drop_table("external_api_control")
    op.drop_index("ix_consulta_cnpjs_queue", table_name="consulta_cnpjs")
    op.drop_index("ix_consulta_cnpjs_job_id", table_name="consulta_cnpjs")
    op.drop_table("consulta_cnpjs")
    op.drop_table("consulta_jobs")

