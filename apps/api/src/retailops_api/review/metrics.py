"""Aggregate review-queue statistics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from retailops_api.domain.models.review import ReviewCase, ReviewStatus

OPEN_STATUSES = (ReviewStatus.open.value, ReviewStatus.in_review.value)
DECIDED_STATUSES = (
    ReviewStatus.approved.value,
    ReviewStatus.rejected.value,
    ReviewStatus.corrected.value,
)


@dataclass(frozen=True)
class ReviewMetrics:
    open_cases: int
    decided_cases: int
    approved_cases: int
    rejected_cases: int
    corrected_cases: int
    cancelled_cases: int
    acceptance_rate: float
    rejection_rate: float
    correction_rate: float
    average_review_duration_seconds: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "open_cases": self.open_cases,
            "decided_cases": self.decided_cases,
            "approved_cases": self.approved_cases,
            "rejected_cases": self.rejected_cases,
            "corrected_cases": self.corrected_cases,
            "cancelled_cases": self.cancelled_cases,
            "acceptance_rate": self.acceptance_rate,
            "rejection_rate": self.rejection_rate,
            "correction_rate": self.correction_rate,
            "average_review_duration_seconds": self.average_review_duration_seconds,
        }


def collect_metrics(session: Session) -> ReviewMetrics:
    cases = session.scalars(select(ReviewCase)).all()
    open_cases = sum(1 for item in cases if item.status in OPEN_STATUSES)
    approved = sum(1 for item in cases if item.status == ReviewStatus.approved.value)
    rejected = sum(1 for item in cases if item.status == ReviewStatus.rejected.value)
    corrected = sum(1 for item in cases if item.status == ReviewStatus.corrected.value)
    cancelled = sum(1 for item in cases if item.status == ReviewStatus.cancelled.value)
    decided = approved + rejected + corrected
    durations = [
        duration_seconds(item.opened_at, item.decided_at)
        for item in cases
        if (
            item.status in DECIDED_STATUSES
            and item.opened_at is not None
            and item.decided_at is not None
        )
    ]
    return ReviewMetrics(
        open_cases=open_cases,
        decided_cases=decided,
        approved_cases=approved,
        rejected_cases=rejected,
        corrected_cases=corrected,
        cancelled_cases=cancelled,
        acceptance_rate=_rate(approved, decided),
        rejection_rate=_rate(rejected, decided),
        correction_rate=_rate(corrected, decided),
        average_review_duration_seconds=(
            None if not durations else round(sum(durations) / len(durations), 3)
        ),
    )


def _rate(part: int, whole: int) -> float:
    if whole == 0:
        return 0.0
    return round(part / whole, 4)


def duration_seconds(opened_at: datetime, decided_at: datetime) -> float:
    start = opened_at if opened_at.tzinfo is not None else opened_at.replace(tzinfo=UTC)
    end = decided_at if decided_at.tzinfo is not None else decided_at.replace(tzinfo=UTC)
    return (end - start).total_seconds()
