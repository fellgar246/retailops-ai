"""human review cases

Creates review cases, immutable AI snapshots, human decisions and an
append-only audit log. A case links to one document finding or one
reconciliation exception.

See docs/adr/ADR-009-human-review-audit-feedback.md for the modelling decisions.

Revision ID: a9c4e18f7b21
Revises: e8b1c03d4a29
Create Date: 2026-08-30 17:30:00.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "a9c4e18f7b21"
down_revision: str | None = "e8b1c03d4a29"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _id() -> sa.types.TypeEngine[int]:
    return sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "review_cases",
        sa.Column("id", _id(), autoincrement=True, nullable=False),
        sa.Column("subject_type", sa.String(length=64), nullable=False),
        sa.Column("document_finding_id", _id(), nullable=True),
        sa.Column("reconciliation_exception_id", _id(), nullable=True),
        sa.Column("supplier_id", _id(), nullable=True),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("risk", sa.String(length=16), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=6, scale=4), nullable=True),
        sa.Column("financial_impact", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("recommended_action", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reviewer", sa.String(length=128), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('open', 'in_review', 'approved', 'rejected', 'corrected', 'cancelled')",
            name=op.f("ck_review_cases_status_known"),
        ),
        sa.CheckConstraint(
            "priority IN ('low', 'medium', 'high', 'urgent')",
            name=op.f("ck_review_cases_priority_known"),
        ),
        sa.CheckConstraint(
            "subject_type IN ('document_finding', 'reconciliation_exception')",
            name=op.f("ck_review_cases_subject_type_known"),
        ),
        sa.CheckConstraint(
            "risk IN ('low', 'medium', 'high')",
            name=op.f("ck_review_cases_risk_known"),
        ),
        sa.CheckConstraint(
            "("
            "subject_type = 'document_finding' "
            "AND document_finding_id IS NOT NULL "
            "AND reconciliation_exception_id IS NULL"
            ") OR ("
            "subject_type = 'reconciliation_exception' "
            "AND reconciliation_exception_id IS NOT NULL "
            "AND document_finding_id IS NULL"
            ")",
            name=op.f("ck_review_cases_subject_matches_type"),
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name=op.f("ck_review_cases_confidence_unit_interval"),
        ),
        sa.ForeignKeyConstraint(
            ["document_finding_id"],
            ["document_findings.id"],
            name=op.f("fk_review_cases_document_finding_id_document_findings"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reconciliation_exception_id"],
            ["reconciliation_exceptions.id"],
            name=op.f("fk_review_cases_reconciliation_exception_id_reconciliation_exceptions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["suppliers.id"],
            name=op.f("fk_review_cases_supplier_id_suppliers"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_review_cases")),
        sa.UniqueConstraint(
            "document_finding_id", name=op.f("uq_review_cases_document_finding_id")
        ),
        sa.UniqueConstraint(
            "reconciliation_exception_id",
            name=op.f("uq_review_cases_reconciliation_exception_id"),
        ),
    )
    op.create_index(
        op.f("ix_review_cases_created_at"), "review_cases", ["created_at"], unique=False
    )
    op.create_index(op.f("ix_review_cases_priority"), "review_cases", ["priority"], unique=False)
    op.create_index(op.f("ix_review_cases_risk"), "review_cases", ["risk"], unique=False)
    op.create_index(op.f("ix_review_cases_status"), "review_cases", ["status"], unique=False)
    op.create_index(
        op.f("ix_review_cases_subject_type"), "review_cases", ["subject_type"], unique=False
    )
    op.create_index(
        op.f("ix_review_cases_supplier_id"), "review_cases", ["supplier_id"], unique=False
    )

    op.create_table(
        "review_ai_snapshots",
        sa.Column("id", _id(), autoincrement=True, nullable=False),
        sa.Column("review_case_id", _id(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("prompt_id", sa.String(length=128), nullable=False),
        sa.Column("prompt_version", sa.String(length=32), nullable=False),
        sa.Column("original_output", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=6, scale=4), nullable=False),
        sa.Column("recommendation", sa.String(length=64), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("reference_key", sa.String(length=80), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name=op.f("ck_review_ai_snapshots_confidence_unit_interval"),
        ),
        sa.ForeignKeyConstraint(
            ["review_case_id"],
            ["review_cases.id"],
            name=op.f("fk_review_ai_snapshots_review_case_id_review_cases"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_review_ai_snapshots")),
        sa.UniqueConstraint("review_case_id", name=op.f("uq_review_ai_snapshots_review_case_id")),
    )

    op.create_table(
        "review_decisions",
        sa.Column("id", _id(), autoincrement=True, nullable=False),
        sa.Column("review_case_id", _id(), nullable=False),
        sa.Column("snapshot_id", _id(), nullable=True),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("reviewer", sa.String(length=128), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("accepted_recommendation_ref", sa.String(length=64), nullable=True),
        sa.Column("correction", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "decision IN ('approved', 'rejected', 'corrected')",
            name=op.f("ck_review_decisions_decision_known"),
        ),
        sa.CheckConstraint(
            "decision <> 'rejected' OR (reason IS NOT NULL AND length(reason) > 0)",
            name=op.f("ck_review_decisions_reject_requires_reason"),
        ),
        sa.CheckConstraint(
            "decision <> 'corrected' OR correction IS NOT NULL",
            name=op.f("ck_review_decisions_correct_requires_payload"),
        ),
        sa.ForeignKeyConstraint(
            ["review_case_id"],
            ["review_cases.id"],
            name=op.f("fk_review_decisions_review_case_id_review_cases"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["review_ai_snapshots.id"],
            name=op.f("fk_review_decisions_snapshot_id_review_ai_snapshots"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_review_decisions")),
        sa.UniqueConstraint("review_case_id", name=op.f("uq_review_decisions_review_case_id")),
    )
    op.create_index(
        op.f("ix_review_decisions_snapshot_id"),
        "review_decisions",
        ["snapshot_id"],
        unique=False,
    )

    op.create_table(
        "review_audit_events",
        sa.Column("id", _id(), autoincrement=True, nullable=False),
        sa.Column("review_case_id", _id(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("actor", sa.String(length=128), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "event_type IN ("
            "'created', 'opened', 'assigned', 'approved', 'rejected', "
            "'corrected', 'status_changed'"
            ")",
            name=op.f("ck_review_audit_events_event_type_known"),
        ),
        sa.ForeignKeyConstraint(
            ["review_case_id"],
            ["review_cases.id"],
            name=op.f("fk_review_audit_events_review_case_id_review_cases"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_review_audit_events")),
    )
    op.create_index(
        op.f("ix_review_audit_events_event_type"),
        "review_audit_events",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_review_audit_events_review_case_id"),
        "review_audit_events",
        ["review_case_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_review_audit_events_review_case_id"), table_name="review_audit_events")
    op.drop_index(op.f("ix_review_audit_events_event_type"), table_name="review_audit_events")
    op.drop_table("review_audit_events")
    op.drop_index(op.f("ix_review_decisions_snapshot_id"), table_name="review_decisions")
    op.drop_table("review_decisions")
    op.drop_table("review_ai_snapshots")
    op.drop_index(op.f("ix_review_cases_supplier_id"), table_name="review_cases")
    op.drop_index(op.f("ix_review_cases_subject_type"), table_name="review_cases")
    op.drop_index(op.f("ix_review_cases_status"), table_name="review_cases")
    op.drop_index(op.f("ix_review_cases_risk"), table_name="review_cases")
    op.drop_index(op.f("ix_review_cases_priority"), table_name="review_cases")
    op.drop_index(op.f("ix_review_cases_created_at"), table_name="review_cases")
    op.drop_table("review_cases")
