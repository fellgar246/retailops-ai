from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from retailops_api.db.base import ActiveMixin, Base, IdMixin, TimestampMixin


class JobKind(StrEnum):
    """Work an operator can start from the console."""

    document_intake = "document_intake"
    reconciliation = "reconciliation"
    forecast = "forecast"


class JobState(StrEnum):
    """Where a job is.

    Happy path: ``queued`` → ``running`` → ``succeeded``. ``failed`` is
    terminal once the attempts are exhausted; a run that failed and has
    attempts left returns to ``queued``.
    """

    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


TERMINAL_STATES = frozenset({JobState.succeeded, JobState.failed, JobState.cancelled})

_KINDS = ", ".join(f"'{item.value}'" for item in JobKind)
_STATES = ", ".join(f"'{item.value}'" for item in JobState)


class ProcessingJob(IdMixin, ActiveMixin, TimestampMixin, Base):
    """One unit of asynchronous work.

    The row is the record of truth for state. A queue only delivers the
    identifier; whatever a message says, this row decides what happened.

    ``result`` points at what the job produced — a document, a reconciliation
    run, a forecast run — rather than repeating it, because those records own
    their own detail.
    """

    __tablename__ = "processing_jobs"
    __table_args__ = (
        CheckConstraint(f"kind IN ({_KINDS})", name="job_kind_known"),
        CheckConstraint(f"state IN ({_STATES})", name="job_state_known"),
        CheckConstraint("attempts >= 0", name="job_attempts_not_negative"),
        CheckConstraint("max_attempts >= 1", name="job_max_attempts_positive"),
        # One key per kind, so a resubmitted upload returns the original job
        # instead of paying for the work twice. The name is left to the shared
        # naming convention, which builds it from the columns.
        UniqueConstraint("kind", "idempotency_key"),
        Index("ix_processing_jobs_claimable", "state", "available_at"),
    )

    kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)

    #: Verified subject of whoever started the job, and their display name.
    requested_by_subject: Mapped[str | None] = mapped_column(String(128), nullable=True)
    requested_by: Mapped[str] = mapped_column(String(128), nullable=False)

    #: What the job needs in order to run. Never the payload itself.
    request: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    #: What it produced, once it has.
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)

    #: When the job may next be claimed, and when the current lease expires.
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    leased_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_token: Mapped[str | None] = mapped_column(String(64), nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"ProcessingJob(id={self.id!r}, kind={self.kind!r}, state={self.state!r})"


__all__ = [
    "TERMINAL_STATES",
    "JobKind",
    "JobState",
    "ProcessingJob",
]
