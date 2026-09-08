"""Verified identity on review records and the audit trail."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from retailops_api.identity.types import Principal, Role
from retailops_api.review.audit import list_events
from retailops_api.review.persist import case_view, get_case
from retailops_api.review.workflow import approve_review, start_review
from tests.review_support import finding_case, person


def test_a_decision_records_the_verified_subject(session: Session) -> None:
    case = finding_case(session, supplier_code="SUP-ID-1")
    actor = person("ana")

    start_review(session, case.id, actor=actor)
    approve_review(session, case.id, actor=actor)

    stored = get_case(session, case.id)
    assert stored.reviewer == "ana"
    assert stored.reviewer_subject == "subject-ana"
    assert stored.decisions[0].reviewer_subject == "subject-ana"
    assert case_view(stored).reviewer_verified is True

    events = list_events(session, case.id)
    human = [event for event in events if event.actor == "ana"]
    system = [event for event in events if event.actor == "system"]
    assert human
    assert all(event.actor_subject == "subject-ana" for event in human)
    # The case was opened by the pipeline, so nothing vouched for that actor.
    assert all(event.actor_subject is None for event in system)


def test_an_operator_acting_locally_is_recorded_but_not_verified(session: Session) -> None:
    """A command-line operator has no identity provider behind them, so the
    decision stays auditable without claiming to be verified."""

    case = finding_case(session, supplier_code="SUP-ID-2")
    operator = Principal(
        subject="operator:ana",
        display_name="ana",
        email=None,
        roles=frozenset({Role.reviewer}),
        verified=False,
    )

    start_review(session, case.id, actor=operator)
    approve_review(session, case.id, actor=operator)

    stored = get_case(session, case.id)
    assert stored.reviewer == "ana"
    assert stored.reviewer_subject is None
    assert case_view(stored).reviewer_verified is False
    assert all(event.actor_subject is None for event in list_events(session, case.id))


def test_two_people_sharing_a_display_name_are_kept_apart(session: Session) -> None:
    """The subject, not the name, decides who holds a case."""

    case = finding_case(session, supplier_code="SUP-ID-3")
    first = Principal(
        subject="subject-1", display_name="ana", email=None, roles=frozenset({Role.reviewer})
    )
    second = Principal(
        subject="subject-2", display_name="ana", email=None, roles=frozenset({Role.reviewer})
    )

    start_review(session, case.id, actor=first)
    start_review(session, case.id, actor=first)

    stored = get_case(session, case.id)
    assert stored.reviewer_subject == "subject-1"

    from retailops_api.review.cases import ReviewConflictError

    try:
        start_review(session, case.id, actor=second)
    except ReviewConflictError:
        conflicted = True
    else:
        conflicted = False

    assert conflicted is True


def test_the_api_never_accepts_an_identity_from_the_request(
    api_client: TestClient, session: Session
) -> None:
    case = finding_case(session, supplier_code="SUP-ID-4")

    api_client.post(f"/reviews/{case.id}/start", json={})
    response = api_client.post(
        f"/reviews/{case.id}/approve", json={"reviewer": "someone-else", "comment": "ok"}
    )

    assert response.status_code == 200
    stored = get_case(session, case.id)
    assert stored.reviewer == "Test Reviewer"
    assert stored.reviewer_subject == "test-reviewer"


def test_the_audit_endpoint_reports_whether_an_actor_was_verified(
    api_client: TestClient, session: Session
) -> None:
    case = finding_case(session, supplier_code="SUP-ID-5")
    api_client.post(f"/reviews/{case.id}/start", json={})

    events = api_client.get("/audit").json()["items"]
    human = [event for event in events if event["actor"] == "Test Reviewer"]
    system = [event for event in events if event["actor"] == "system"]

    assert human
    assert all(event["actor_verified"] is True for event in human)
    assert all(event["actor_verified"] is False for event in system)
