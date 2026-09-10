"""processing jobs

Asynchronous work an operator starts from the console. The row is the record
of truth for state; a queue only delivers the identifier.

The unique key on (kind, idempotency_key) is what stops a resubmitted upload
from being processed, and paid for, twice.

Revision ID: c1e7a4b09d35
Revises: b5d3f70c9a14
Create Date: 2026-09-09 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c1e7a4b09d35"
down_revision: str | None = "b5d3f70c9a14"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_KINDS = "'document_intake', 'reconciliation', 'forecast'"
_STATES = "'queued', 'running', 'succeeded', 'failed', 'cancelled'"


def _id() -> sa.types.TypeEngine[int]:
    return sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "processing_jobs",
        sa.Column("id", _id(), autoincrement=True, nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("requested_by_subject", sa.String(length=128), nullable=True),
        sa.Column("requested_by", sa.String(length=128), nullable=False),
        sa.Column("request", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default=sa.text("3")),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("leased_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_token", sa.String(length=64), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(f"kind IN ({_KINDS})", name="job_kind_known"),
        sa.CheckConstraint(f"state IN ({_STATES})", name="job_state_known"),
        sa.CheckConstraint("attempts >= 0", name="job_attempts_not_negative"),
        sa.CheckConstraint("max_attempts >= 1", name="job_max_attempts_positive"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "kind", "idempotency_key", name="uq_processing_jobs_kind_idempotency_key"
        ),
    )
    op.create_index("ix_processing_jobs_kind", "processing_jobs", ["kind"])
    op.create_index("ix_processing_jobs_state", "processing_jobs", ["state"])
    op.create_index("ix_processing_jobs_claimable", "processing_jobs", ["state", "available_at"])


def downgrade() -> None:
    op.drop_index("ix_processing_jobs_claimable", table_name="processing_jobs")
    op.drop_index("ix_processing_jobs_state", table_name="processing_jobs")
    op.drop_index("ix_processing_jobs_kind", table_name="processing_jobs")
    op.drop_table("processing_jobs")
