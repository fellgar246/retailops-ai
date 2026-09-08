from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from retailops_api.db.base import (
    ActiveMixin,
    Base,
    CreatedAtMixin,
    IdMixin,
    IdType,
    Money,
    TimestampMixin,
)

if TYPE_CHECKING:
    from retailops_api.domain.models.document import DocumentFinding
    from retailops_api.domain.models.reconciliation import ReconciliationException
    from retailops_api.domain.models.supplier import Supplier


class ReviewStatus(StrEnum):
    open = "open"
    in_review = "in_review"
    approved = "approved"
    rejected = "rejected"
    corrected = "corrected"
    cancelled = "cancelled"


class ReviewDecision(StrEnum):
    approved = "approved"
    rejected = "rejected"
    corrected = "corrected"


class ReviewPriority(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"


class ReviewSubjectType(StrEnum):
    document_finding = "document_finding"
    reconciliation_exception = "reconciliation_exception"


class ReviewEventType(StrEnum):
    created = "created"
    opened = "opened"
    assigned = "assigned"
    approved = "approved"
    rejected = "rejected"
    corrected = "corrected"
    status_changed = "status_changed"


_STATUSES = ", ".join(f"'{item.value}'" for item in ReviewStatus)
_DECISIONS = ", ".join(f"'{item.value}'" for item in ReviewDecision)
_PRIORITIES = ", ".join(f"'{item.value}'" for item in ReviewPriority)
_SUBJECTS = ", ".join(f"'{item.value}'" for item in ReviewSubjectType)
_EVENTS = ", ".join(f"'{item.value}'" for item in ReviewEventType)
_RISKS = "'low', 'medium', 'high'"


class ReviewCase(IdMixin, ActiveMixin, TimestampMixin, Base):
    """A human-oversight item linked to a finding or a reconciliation exception.

    Status moves only through the documented transitions. AI output lives on
    an immutable snapshot; the human decision is a separate row. Audit events
    are appended and never rewritten.
    """

    __tablename__ = "review_cases"
    __table_args__ = (
        CheckConstraint(f"status IN ({_STATUSES})", name="status_known"),
        CheckConstraint(f"priority IN ({_PRIORITIES})", name="priority_known"),
        CheckConstraint(f"subject_type IN ({_SUBJECTS})", name="subject_type_known"),
        CheckConstraint(f"risk IN ({_RISKS})", name="risk_known"),
        CheckConstraint(
            "("
            "subject_type = 'document_finding' "
            "AND document_finding_id IS NOT NULL "
            "AND reconciliation_exception_id IS NULL"
            ") OR ("
            "subject_type = 'reconciliation_exception' "
            "AND reconciliation_exception_id IS NOT NULL "
            "AND document_finding_id IS NULL"
            ")",
            name="subject_matches_type",
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="confidence_unit_interval",
        ),
        Index("ix_review_cases_created_at", "created_at"),
    )

    subject_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    document_finding_id: Mapped[int | None] = mapped_column(
        IdType,
        ForeignKey("document_findings.id", ondelete="RESTRICT"),
        nullable=True,
        unique=True,
    )
    reconciliation_exception_id: Mapped[int | None] = mapped_column(
        IdType,
        ForeignKey("reconciliation_exceptions.id", ondelete="RESTRICT"),
        nullable=True,
        unique=True,
    )
    supplier_id: Mapped[int | None] = mapped_column(
        IdType, ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    priority: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    risk: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(6, 4, asdecimal=True), nullable=True)
    financial_impact: Mapped[Decimal] = mapped_column(Money, nullable=False)
    recommended_action: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    reviewer: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Null on records written before authentication existed. Those decisions
    # carry an unverified display name only and must not be shown as verified.
    reviewer_subject: Mapped[str | None] = mapped_column(String(128), nullable=True)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    document_finding: Mapped[DocumentFinding | None] = relationship()
    reconciliation_exception: Mapped[ReconciliationException | None] = relationship()
    supplier: Mapped[Supplier | None] = relationship()
    snapshots: Mapped[list[ReviewAISnapshot]] = relationship(
        back_populates="review_case", cascade="all, delete-orphan"
    )
    decisions: Mapped[list[ReviewDecisionRecord]] = relationship(
        back_populates="review_case", cascade="all, delete-orphan"
    )
    audit_events: Mapped[list[ReviewAuditEvent]] = relationship(
        back_populates="review_case", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"ReviewCase(id={self.id!r}, subject_type={self.subject_type!r}, "
            f"status={self.status!r})"
        )


class ReviewAISnapshot(IdMixin, CreatedAtMixin, Base):
    """Immutable copy of the reviewer output that opened a case.

    Rows are inserted once. There is no ``updated_at``: a later model call
    is a new snapshot, never an edit of this one.
    """

    __tablename__ = "review_ai_snapshots"
    __table_args__ = (
        UniqueConstraint("review_case_id"),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="confidence_unit_interval",
        ),
    )

    review_case_id: Mapped[int] = mapped_column(
        IdType, ForeignKey("review_cases.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_id: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False)
    original_output: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(6, 4, asdecimal=True), nullable=False)
    recommendation: Mapped[str] = mapped_column(String(64), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    reference_key: Mapped[str] = mapped_column(String(80), nullable=False)

    review_case: Mapped[ReviewCase] = relationship(back_populates="snapshots")

    def __repr__(self) -> str:
        return (
            f"ReviewAISnapshot(review_case_id={self.review_case_id!r}, "
            f"provider={self.provider!r}, model={self.model!r})"
        )


class ReviewDecisionRecord(IdMixin, CreatedAtMixin, Base):
    """The human close of a case: approve, reject or correct.

    One row per case. The original AI recommendation stays on the snapshot;
    a correction stores the structured values the reviewer supplied.
    """

    __tablename__ = "review_decisions"
    __table_args__ = (
        UniqueConstraint("review_case_id"),
        CheckConstraint(f"decision IN ({_DECISIONS})", name="decision_known"),
        CheckConstraint(
            "decision <> 'rejected' OR (reason IS NOT NULL AND length(reason) > 0)",
            name="reject_requires_reason",
        ),
        CheckConstraint(
            "decision <> 'corrected' OR correction IS NOT NULL",
            name="correct_requires_payload",
        ),
    )

    review_case_id: Mapped[int] = mapped_column(
        IdType, ForeignKey("review_cases.id", ondelete="CASCADE"), nullable=False
    )
    snapshot_id: Mapped[int | None] = mapped_column(
        IdType,
        ForeignKey("review_ai_snapshots.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    reviewer: Mapped[str] = mapped_column(String(128), nullable=False)
    reviewer_subject: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    accepted_recommendation_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    correction: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    review_case: Mapped[ReviewCase] = relationship(back_populates="decisions")
    snapshot: Mapped[ReviewAISnapshot | None] = relationship()

    def __repr__(self) -> str:
        return (
            f"ReviewDecisionRecord(review_case_id={self.review_case_id!r}, "
            f"decision={self.decision!r})"
        )


class ReviewAuditEvent(IdMixin, CreatedAtMixin, Base):
    """One append-only event in a case's history. Existing rows are not updated."""

    __tablename__ = "review_audit_events"
    __table_args__ = (CheckConstraint(f"event_type IN ({_EVENTS})", name="event_type_known"),)

    review_case_id: Mapped[int] = mapped_column(
        IdType,
        ForeignKey("review_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    actor_subject: Mapped[str | None] = mapped_column(String(128), nullable=True)
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    review_case: Mapped[ReviewCase] = relationship(back_populates="audit_events")

    def __repr__(self) -> str:
        return (
            f"ReviewAuditEvent(review_case_id={self.review_case_id!r}, "
            f"event_type={self.event_type!r})"
        )
