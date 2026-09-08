"""Human review domain: statuses, transitions, errors and queue DTOs.

A case starts ``open``, moves to ``in_review`` when someone picks it up, and
closes as ``approved``, ``rejected``, ``corrected`` or ``cancelled``. Terminal
statuses do not leave those states.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from retailops_api.domain.models.review import (
    ReviewDecision,
    ReviewEventType,
    ReviewPriority,
    ReviewStatus,
    ReviewSubjectType,
)
from retailops_api.review.types import RiskLevel

HIGH_IMPACT = Decimal("100.0000")
URGENT_IMPACT = Decimal("1000.0000")
MEDIUM_IMPACT = Decimal("10.0000")
CONFIDENCE_QUANT = Decimal("0.0001")

ALLOWED_TRANSITIONS: dict[ReviewStatus, frozenset[ReviewStatus]] = {
    ReviewStatus.open: frozenset({ReviewStatus.in_review, ReviewStatus.cancelled}),
    ReviewStatus.in_review: frozenset(
        {
            ReviewStatus.approved,
            ReviewStatus.rejected,
            ReviewStatus.corrected,
            ReviewStatus.cancelled,
        }
    ),
    ReviewStatus.approved: frozenset(),
    ReviewStatus.rejected: frozenset(),
    ReviewStatus.corrected: frozenset(),
    ReviewStatus.cancelled: frozenset(),
}

PRIORITY_RANK = {
    ReviewPriority.urgent: 4,
    ReviewPriority.high: 3,
    ReviewPriority.medium: 2,
    ReviewPriority.low: 1,
}

CORRECTION_KEYS = frozenset({"suggested_value", "recommended_action", "risk", "summary", "fields"})


class ReviewWorkflowError(ValueError):
    """Base error for human-review persistence and transitions."""


class ReviewNotFoundError(ReviewWorkflowError):
    """The requested case, finding or exception does not exist."""


class ReviewConflictError(ReviewWorkflowError):
    """The case is not in a state that allows this transition."""

    def __init__(
        self,
        message: str,
        *,
        current: ReviewStatus,
        attempted: ReviewStatus | str,
    ) -> None:
        super().__init__(message)
        self.current = current
        self.attempted = attempted


class ReviewValidationError(ReviewWorkflowError):
    """The request is structurally invalid (missing reason, empty reviewer, …)."""


def can_transition(current: ReviewStatus, target: ReviewStatus) -> bool:
    return target in ALLOWED_TRANSITIONS[current]


def assert_transition(current: ReviewStatus, target: ReviewStatus) -> None:
    if can_transition(current, target):
        return
    raise ReviewConflictError(
        f"cannot move a {current.value} case to {target.value}",
        current=current,
        attempted=target,
    )


def all_transition_pairs() -> tuple[tuple[ReviewStatus, ReviewStatus, bool], ...]:
    """Every status pair and whether the move is allowed. Used by tests."""

    statuses = tuple(ReviewStatus)
    return tuple(
        (source, target, can_transition(source, target))
        for source in statuses
        for target in statuses
    )


def derive_priority(risk: RiskLevel, financial_impact: Decimal) -> ReviewPriority:
    impact = abs(financial_impact)
    if impact >= URGENT_IMPACT or (risk is RiskLevel.high and impact >= HIGH_IMPACT):
        return ReviewPriority.urgent
    if risk is RiskLevel.high or impact >= HIGH_IMPACT:
        return ReviewPriority.high
    if risk is RiskLevel.medium or impact >= MEDIUM_IMPACT:
        return ReviewPriority.medium
    return ReviewPriority.low


def risk_from_severity(severity: str) -> RiskLevel:
    if severity == "error":
        return RiskLevel.high
    if severity == "warning":
        return RiskLevel.medium
    return RiskLevel.low


def as_confidence(value: float | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(CONFIDENCE_QUANT)


def parse_correction(raw: dict[str, Any]) -> dict[str, Any]:
    unknown = set(raw) - CORRECTION_KEYS
    if unknown:
        raise ReviewValidationError(f"unknown correction fields: {', '.join(sorted(unknown))}")
    suggested = raw.get("suggested_value")
    action = raw.get("recommended_action")
    risk = raw.get("risk")
    summary = raw.get("summary")
    fields = raw.get("fields")
    if fields is None:
        fields = {}
    if not isinstance(fields, dict):
        raise ReviewValidationError("correction.fields must be an object")
    if not any((suggested, action, risk, summary, fields)):
        raise ReviewValidationError("correction must include at least one value")
    payload: dict[str, Any] = {"fields": {str(key): str(value) for key, value in fields.items()}}
    if suggested is not None:
        payload["suggested_value"] = str(suggested)
    if action is not None:
        payload["recommended_action"] = str(action)
    if risk is not None:
        payload["risk"] = str(risk)
    if summary is not None:
        payload["summary"] = str(summary)
    return payload


def require_reason(reason: str) -> str:
    text = reason.strip()
    if not text:
        raise ReviewValidationError("a reason is required when rejecting a case")
    return text


def reference_key(subject_type: ReviewSubjectType, subject_id: int) -> str:
    return f"{subject_type.value}:{subject_id}"


@dataclass(frozen=True)
class ReviewFilters:
    statuses: tuple[ReviewStatus, ...] = ()
    priorities: tuple[ReviewPriority, ...] = ()
    subject_types: tuple[ReviewSubjectType, ...] = ()
    supplier_id: int | None = None
    risks: tuple[RiskLevel, ...] = ()
    created_from: date | datetime | None = None
    created_to: date | datetime | None = None


@dataclass(frozen=True)
class ReviewCaseView:
    id: int
    subject_type: ReviewSubjectType
    document_finding_id: int | None
    reconciliation_exception_id: int | None
    supplier_id: int | None
    priority: ReviewPriority
    risk: RiskLevel
    confidence: Decimal | None
    financial_impact: Decimal
    recommended_action: str | None
    status: ReviewStatus
    reviewer: str | None
    #: True when an identity provider vouched for the reviewer. Cases decided
    #: before authentication existed report False.
    reviewer_verified: bool
    opened_at: datetime | None
    decided_at: datetime | None
    created_at: datetime
    updated_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "subject_type": self.subject_type.value,
            "document_finding_id": self.document_finding_id,
            "reconciliation_exception_id": self.reconciliation_exception_id,
            "supplier_id": self.supplier_id,
            "priority": self.priority.value,
            "risk": self.risk.value,
            "confidence": None if self.confidence is None else str(self.confidence),
            "financial_impact": str(self.financial_impact),
            "recommended_action": self.recommended_action,
            "status": self.status.value,
            "reviewer_verified": self.reviewer_verified,
            "reviewer": self.reviewer,
            "opened_at": _iso(self.opened_at),
            "decided_at": _iso(self.decided_at),
            "created_at": _iso(self.created_at),
            "updated_at": _iso(self.updated_at),
        }


@dataclass(frozen=True)
class ReviewPage:
    items: tuple[ReviewCaseView, ...]
    total: int
    limit: int
    offset: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "items": [item.to_dict() for item in self.items],
            "total": self.total,
            "limit": self.limit,
            "offset": self.offset,
        }


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


__all__ = [
    "ALLOWED_TRANSITIONS",
    "CORRECTION_KEYS",
    "PRIORITY_RANK",
    "ReviewCaseView",
    "ReviewConflictError",
    "ReviewDecision",
    "ReviewEventType",
    "ReviewFilters",
    "ReviewNotFoundError",
    "ReviewPage",
    "ReviewPriority",
    "ReviewStatus",
    "ReviewSubjectType",
    "ReviewValidationError",
    "ReviewWorkflowError",
    "all_transition_pairs",
    "as_confidence",
    "assert_transition",
    "can_transition",
    "derive_priority",
    "parse_correction",
    "reference_key",
    "require_reason",
    "risk_from_severity",
]
