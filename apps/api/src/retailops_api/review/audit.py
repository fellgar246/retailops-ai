"""Append-only review history. Callers never update or delete events."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from retailops_api.domain.models.review import ReviewAuditEvent, ReviewCase, ReviewEventType
from retailops_api.review.cases import ReviewStatus


def append_event(
    session: Session,
    case: ReviewCase,
    *,
    event_type: ReviewEventType,
    actor: str,
    from_status: ReviewStatus | None = None,
    to_status: ReviewStatus | None = None,
    payload: dict[str, Any] | None = None,
    occurred_at: datetime | None = None,
) -> ReviewAuditEvent:
    event = ReviewAuditEvent(
        review_case_id=case.id,
        event_type=event_type.value,
        actor=actor,
        from_status=None if from_status is None else from_status.value,
        to_status=None if to_status is None else to_status.value,
        payload=payload,
    )
    if occurred_at is not None:
        event.created_at = occurred_at
    case.audit_events.append(event)
    session.flush()
    return event


def list_events(session: Session, case_id: int) -> list[ReviewAuditEvent]:
    from sqlalchemy import select

    return list(
        session.scalars(
            select(ReviewAuditEvent)
            .where(ReviewAuditEvent.review_case_id == case_id)
            .order_by(ReviewAuditEvent.id.asc())
        ).all()
    )


def list_recent_events(
    session: Session, *, limit: int, offset: int
) -> tuple[list[ReviewAuditEvent], int]:
    from sqlalchemy import func, select

    total = session.scalar(select(func.count()).select_from(ReviewAuditEvent)) or 0
    events = list(
        session.scalars(
            select(ReviewAuditEvent)
            .order_by(ReviewAuditEvent.created_at.desc(), ReviewAuditEvent.id.desc())
            .limit(limit)
            .offset(offset)
        ).all()
    )
    return events, total
