"""Controlled review transitions. Does not commit.

Start moves ``open`` to ``in_review`` and records the reviewer. Approve,
reject and correct require an active review. A second writer that sees a
different status is rejected rather than overwriting the first decision.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from retailops_api.domain.models.review import (
    ReviewCase,
    ReviewDecision,
    ReviewDecisionRecord,
    ReviewEventType,
    ReviewStatus,
)
from retailops_api.review.audit import append_event
from retailops_api.review.cases import (
    ReviewConflictError,
    ReviewValidationError,
    assert_transition,
    parse_correction,
    require_reason,
    require_reviewer,
)
from retailops_api.review.persist import get_case, snapshot_for


def start_review(
    session: Session,
    case_id: int,
    *,
    reviewer: str,
    occurred_at: datetime | None = None,
) -> ReviewCase:
    case = get_case(session, case_id)
    actor = require_reviewer(reviewer)
    current = ReviewStatus(case.status)
    if current is ReviewStatus.in_review and case.reviewer == actor:
        return case
    if current is ReviewStatus.in_review:
        raise ReviewConflictError(
            f"case {case.id} is already in review by {case.reviewer}",
            current=current,
            attempted=ReviewStatus.in_review,
        )
    assert_transition(current, ReviewStatus.in_review)
    when = occurred_at or datetime.now(UTC)
    case.reviewer = actor
    case.opened_at = when
    case.status = ReviewStatus.in_review.value
    _status_changed(session, case, actor, current, ReviewStatus.in_review, when)
    append_event(
        session,
        case,
        event_type=ReviewEventType.opened,
        actor=actor,
        from_status=current,
        to_status=ReviewStatus.in_review,
        occurred_at=when,
    )
    append_event(
        session,
        case,
        event_type=ReviewEventType.assigned,
        actor=actor,
        from_status=ReviewStatus.in_review,
        to_status=ReviewStatus.in_review,
        payload={"reviewer": actor},
        occurred_at=when,
    )
    session.flush()
    return case


def assign_review(
    session: Session,
    case_id: int,
    *,
    reviewer: str,
    occurred_at: datetime | None = None,
) -> ReviewCase:
    case = get_case(session, case_id)
    actor = require_reviewer(reviewer)
    current = ReviewStatus(case.status)
    if current is ReviewStatus.open:
        return start_review(session, case_id, reviewer=actor, occurred_at=occurred_at)
    if current is not ReviewStatus.in_review:
        raise ReviewConflictError(
            f"cannot assign a {current.value} case",
            current=current,
            attempted="assign",
        )
    if case.reviewer == actor:
        return case
    when = occurred_at or datetime.now(UTC)
    previous = case.reviewer
    case.reviewer = actor
    append_event(
        session,
        case,
        event_type=ReviewEventType.assigned,
        actor=actor,
        from_status=current,
        to_status=current,
        payload={"reviewer": actor, "previous_reviewer": previous},
        occurred_at=when,
    )
    session.flush()
    return case


def approve_review(
    session: Session,
    case_id: int,
    *,
    reviewer: str,
    comment: str | None = None,
    snapshot_id: int | None = None,
    occurred_at: datetime | None = None,
) -> ReviewCase:
    case = get_case(session, case_id)
    actor = require_reviewer(reviewer)
    snapshot = _snapshot(case, snapshot_id)
    ref = None if snapshot is None else f"snapshot:{snapshot.id}"
    return _close(
        session,
        case,
        actor=actor,
        target=ReviewStatus.approved,
        decision=ReviewDecision.approved,
        event_type=ReviewEventType.approved,
        comment=_optional_text(comment),
        reason=None,
        correction=None,
        snapshot_id=None if snapshot is None else snapshot.id,
        accepted_recommendation_ref=ref,
        occurred_at=occurred_at,
    )


def reject_review(
    session: Session,
    case_id: int,
    *,
    reviewer: str,
    reason: str,
    comment: str | None = None,
    occurred_at: datetime | None = None,
) -> ReviewCase:
    case = get_case(session, case_id)
    actor = require_reviewer(reviewer)
    snapshot = snapshot_for(case)
    return _close(
        session,
        case,
        actor=actor,
        target=ReviewStatus.rejected,
        decision=ReviewDecision.rejected,
        event_type=ReviewEventType.rejected,
        comment=_optional_text(comment),
        reason=require_reason(reason),
        correction=None,
        snapshot_id=None if snapshot is None else snapshot.id,
        accepted_recommendation_ref=None,
        occurred_at=occurred_at,
    )


def correct_review(
    session: Session,
    case_id: int,
    *,
    reviewer: str,
    correction: dict[str, Any],
    comment: str | None = None,
    occurred_at: datetime | None = None,
) -> ReviewCase:
    case = get_case(session, case_id)
    actor = require_reviewer(reviewer)
    payload = parse_correction(correction)
    snapshot = snapshot_for(case)
    return _close(
        session,
        case,
        actor=actor,
        target=ReviewStatus.corrected,
        decision=ReviewDecision.corrected,
        event_type=ReviewEventType.corrected,
        comment=_optional_text(comment),
        reason=None,
        correction=payload,
        snapshot_id=None if snapshot is None else snapshot.id,
        accepted_recommendation_ref=None,
        occurred_at=occurred_at,
    )


def cancel_review(
    session: Session,
    case_id: int,
    *,
    reviewer: str,
    comment: str | None = None,
    occurred_at: datetime | None = None,
) -> ReviewCase:
    case = get_case(session, case_id)
    actor = require_reviewer(reviewer)
    current = ReviewStatus(case.status)
    assert_transition(current, ReviewStatus.cancelled)
    when = occurred_at or datetime.now(UTC)
    case.reviewer = actor
    case.status = ReviewStatus.cancelled.value
    case.decided_at = when
    _status_changed(
        session,
        case,
        actor,
        current,
        ReviewStatus.cancelled,
        when,
        payload={"comment": _optional_text(comment)} if comment else None,
    )
    session.flush()
    return case


def _close(
    session: Session,
    case: ReviewCase,
    *,
    actor: str,
    target: ReviewStatus,
    decision: ReviewDecision,
    event_type: ReviewEventType,
    comment: str | None,
    reason: str | None,
    correction: dict[str, Any] | None,
    snapshot_id: int | None,
    accepted_recommendation_ref: str | None,
    occurred_at: datetime | None,
) -> ReviewCase:
    current = ReviewStatus(case.status)
    assert_transition(current, target)
    if case.decisions:
        raise ReviewConflictError(
            f"case {case.id} already has a decision",
            current=current,
            attempted=target,
        )
    when = occurred_at or datetime.now(UTC)
    case.reviewer = actor
    case.status = target.value
    case.decided_at = when
    record = ReviewDecisionRecord(
        review_case_id=case.id,
        snapshot_id=snapshot_id,
        decision=decision.value,
        reviewer=actor,
        reason=reason,
        comment=comment,
        accepted_recommendation_ref=accepted_recommendation_ref,
        correction=correction,
        created_at=when,
    )
    case.decisions.append(record)
    _status_changed(session, case, actor, current, target, when)
    append_event(
        session,
        case,
        event_type=event_type,
        actor=actor,
        from_status=current,
        to_status=target,
        payload=_decision_payload(reason, comment, correction, accepted_recommendation_ref),
        occurred_at=when,
    )
    session.flush()
    return case


def _snapshot(case: ReviewCase, snapshot_id: int | None) -> Any:
    original = snapshot_for(case)
    if snapshot_id is None:
        return original
    match = next((item for item in case.snapshots if item.id == snapshot_id), None)
    if match is None:
        raise ReviewValidationError(f"snapshot {snapshot_id} does not belong to case {case.id}")
    return match


def _status_changed(
    session: Session,
    case: ReviewCase,
    actor: str,
    current: ReviewStatus,
    target: ReviewStatus,
    when: datetime,
    payload: dict[str, Any] | None = None,
) -> None:
    append_event(
        session,
        case,
        event_type=ReviewEventType.status_changed,
        actor=actor,
        from_status=current,
        to_status=target,
        payload=payload,
        occurred_at=when,
    )


def _decision_payload(
    reason: str | None,
    comment: str | None,
    correction: dict[str, Any] | None,
    accepted_recommendation_ref: str | None,
) -> dict[str, Any] | None:
    payload: dict[str, Any] = {}
    if reason is not None:
        payload["reason"] = reason
    if comment is not None:
        payload["comment"] = comment
    if correction is not None:
        payload["correction"] = correction
    if accepted_recommendation_ref is not None:
        payload["accepted_recommendation_ref"] = accepted_recommendation_ref
    return payload or None


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None
