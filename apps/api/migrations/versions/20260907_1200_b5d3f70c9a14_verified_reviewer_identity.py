"""verified reviewer identity

Adds the stable subject identifier that authenticated review decisions and
audit events point at, alongside the existing display name.

Existing rows keep a null subject on purpose. They were written when the
reviewer name was supplied by the client and never verified, so they must stay
distinguishable from authenticated records rather than be backfilled with an
identifier that would look genuine.

Revision ID: b5d3f70c9a14
Revises: a9c4e18f7b21
Create Date: 2026-09-07 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b5d3f70c9a14"
down_revision: str | None = "a9c4e18f7b21"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "review_cases",
        sa.Column("reviewer_subject", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "review_decisions",
        sa.Column("reviewer_subject", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "review_audit_events",
        sa.Column("actor_subject", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("review_audit_events", "actor_subject")
    op.drop_column("review_decisions", "reviewer_subject")
    op.drop_column("review_cases", "reviewer_subject")
