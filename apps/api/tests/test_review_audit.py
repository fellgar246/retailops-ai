"""Audit events are appended and never rewritten."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from retailops_api.domain.models.review import ReviewAuditEvent, ReviewEventType
from retailops_api.review.audit import list_events
from retailops_api.review.workflow import approve_review, assign_review, start_review
from tests.review_support import finding_case


def test_start_and_approve_append_the_documented_events(session: Session) -> None:
    case = finding_case(session, supplier_code="SUP-EVT")
    start_review(session, case.id, reviewer="alice")
    approve_review(session, case.id, reviewer="alice", comment="ok")

    types = [event.event_type for event in list_events(session, case.id)]
    assert types == [
        ReviewEventType.created.value,
        ReviewEventType.status_changed.value,
        ReviewEventType.opened.value,
        ReviewEventType.assigned.value,
        ReviewEventType.status_changed.value,
        ReviewEventType.approved.value,
    ]
    changed = [
        event for event in list_events(session, case.id) if event.event_type == "status_changed"
    ]
    assert changed[0].from_status == "open"
    assert changed[0].to_status == "in_review"
    assert changed[1].from_status == "in_review"
    assert changed[1].to_status == "approved"


def test_reassign_appends_without_replacing_history(session: Session) -> None:
    case = finding_case(session, supplier_code="SUP-HIST")
    start_review(session, case.id, reviewer="alice")
    before = list(list_events(session, case.id))
    assign_review(session, case.id, reviewer="bob")
    after = list(list_events(session, case.id))

    assert [event.id for event in before] == [event.id for event in after[: len(before)]]
    assert after[-1].event_type == ReviewEventType.assigned.value
    assert after[-1].payload is not None
    assert after[-1].payload["reviewer"] == "bob"
    assert after[-1].payload["previous_reviewer"] == "alice"
    assert len(session.scalars(select(ReviewAuditEvent)).all()) == len(after)
