"""Review metrics: open count, rates and average duration."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from retailops_api.review.metrics import collect_metrics
from retailops_api.review.workflow import (
    approve_review,
    cancel_review,
    correct_review,
    reject_review,
    start_review,
)
from tests.review_support import finding_case, person


def test_metrics_with_no_cases_are_zero(session: Session) -> None:
    metrics = collect_metrics(session)
    assert metrics.open_cases == 0
    assert metrics.decided_cases == 0
    assert metrics.acceptance_rate == 0.0
    assert metrics.average_review_duration_seconds is None


def test_metrics_count_open_cases_and_decision_rates(session: Session) -> None:
    opened = datetime(2026, 8, 30, 10, 0, tzinfo=UTC)
    hour = timedelta(hours=1)

    finding_case(session, supplier_code="SUP-M1")
    active = finding_case(session, supplier_code="SUP-M2")
    start_review(session, active.id, actor=person("alice"), occurred_at=opened)

    approved = finding_case(session, supplier_code="SUP-M3")
    start_review(session, approved.id, actor=person("alice"), occurred_at=opened)
    approve_review(session, approved.id, actor=person("alice"), occurred_at=opened + hour)

    rejected = finding_case(session, supplier_code="SUP-M4")
    start_review(session, rejected.id, actor=person("alice"), occurred_at=opened)
    reject_review(
        session,
        rejected.id,
        actor=person("alice"),
        reason="no",
        occurred_at=opened + (2 * hour),
    )

    corrected = finding_case(session, supplier_code="SUP-M5")
    start_review(session, corrected.id, actor=person("alice"), occurred_at=opened)
    correct_review(
        session,
        corrected.id,
        actor=person("alice"),
        correction={"suggested_value": "BEV-WATER"},
        occurred_at=opened + (3 * hour),
    )

    cancelled = finding_case(session, supplier_code="SUP-M6")
    cancel_review(session, cancelled.id, actor=person("alice"))

    metrics = collect_metrics(session)
    assert metrics.open_cases == 2
    assert metrics.decided_cases == 3
    assert metrics.approved_cases == 1
    assert metrics.rejected_cases == 1
    assert metrics.corrected_cases == 1
    assert metrics.cancelled_cases == 1
    assert metrics.acceptance_rate == 0.3333
    assert metrics.rejection_rate == 0.3333
    assert metrics.correction_rate == 0.3333
    assert metrics.average_review_duration_seconds == 7200.0
