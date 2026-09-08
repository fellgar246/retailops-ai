"""Start, assign, approve, reject, correct and conflicting transitions."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from retailops_api.domain.models.review import ReviewDecision, ReviewStatus
from retailops_api.identity.types import InvalidTokenError, Principal
from retailops_api.review.cases import ReviewConflictError, ReviewValidationError
from retailops_api.review.persist import get_case, snapshot_for
from retailops_api.review.workflow import (
    approve_review,
    assign_review,
    cancel_review,
    correct_review,
    reject_review,
    start_review,
)
from tests.review_support import finding_case, person


def test_start_moves_open_to_in_review(session: Session) -> None:
    case = finding_case(session, supplier_code="SUP-START")
    started = start_review(session, case.id, actor=person("alice"))

    assert started.status == ReviewStatus.in_review.value
    assert started.reviewer == "alice"
    assert started.opened_at is not None


def test_start_is_idempotent_for_the_same_reviewer(session: Session) -> None:
    case = finding_case(session, supplier_code="SUP-IDEM")
    start_review(session, case.id, actor=person("alice"))
    again = start_review(session, case.id, actor=person("alice"))

    assert again.status == ReviewStatus.in_review.value
    assert again.reviewer == "alice"


def test_start_conflicts_when_another_reviewer_holds_the_case(session: Session) -> None:
    case = finding_case(session, supplier_code="SUP-HOLD")
    start_review(session, case.id, actor=person("alice"))

    with pytest.raises(ReviewConflictError):
        start_review(session, case.id, actor=person("bob"))


def test_assign_hands_an_active_case_to_someone_else(session: Session) -> None:
    case = finding_case(session, supplier_code="SUP-ASGN")
    start_review(session, case.id, actor=person("alice"))
    assigned = assign_review(session, case.id, actor=person("bob"))

    assert assigned.reviewer == "bob"
    assert assigned.status == ReviewStatus.in_review.value


def test_approve_records_reviewer_comment_and_recommendation_ref(session: Session) -> None:
    case = finding_case(session, supplier_code="SUP-OK")
    start_review(session, case.id, actor=person("alice"))
    approved = approve_review(session, case.id, actor=person("alice"), comment="looks right")
    loaded = get_case(session, approved.id)
    decision = loaded.decisions[0]
    snapshot = snapshot_for(loaded)

    assert loaded.status == ReviewStatus.approved.value
    assert decision.decision == ReviewDecision.approved.value
    assert decision.reviewer == "alice"
    assert decision.comment == "looks right"
    assert snapshot is not None
    assert decision.accepted_recommendation_ref == f"snapshot:{snapshot.id}"
    assert loaded.decided_at is not None


def test_reject_requires_a_reason(session: Session) -> None:
    case = finding_case(session, supplier_code="SUP-NO")
    start_review(session, case.id, actor=person("alice"))

    with pytest.raises(ReviewValidationError):
        reject_review(session, case.id, actor=person("alice"), reason="  ")

    rejected = reject_review(
        session, case.id, actor=person("alice"), reason="wrong category", comment="see ticket"
    )
    loaded = get_case(session, rejected.id)
    assert loaded.status == ReviewStatus.rejected.value
    assert loaded.decisions[0].reason == "wrong category"
    assert loaded.decisions[0].comment == "see ticket"


def test_correct_keeps_original_ai_and_human_values(session: Session) -> None:
    case = finding_case(session, supplier_code="SUP-FIX", suggested_value="BEV-SOFT")
    start_review(session, case.id, actor=person("alice"))
    corrected = correct_review(
        session,
        case.id,
        actor=person("alice"),
        correction={"suggested_value": "BEV-WATER", "summary": "catalog water"},
    )
    loaded = get_case(session, corrected.id)
    snapshot = snapshot_for(loaded)
    decision = loaded.decisions[0]

    assert loaded.status == ReviewStatus.corrected.value
    assert snapshot is not None
    assert snapshot.original_output["suggested_value"] == "BEV-SOFT"
    assert decision.correction is not None
    assert decision.correction["suggested_value"] == "BEV-WATER"
    assert decision.correction["summary"] == "catalog water"


def test_cannot_approve_an_open_case(session: Session) -> None:
    case = finding_case(session, supplier_code="SUP-SKIP")

    with pytest.raises(ReviewConflictError):
        approve_review(session, case.id, actor=person("alice"))


def test_cannot_decide_twice(session: Session) -> None:
    case = finding_case(session, supplier_code="SUP-TWICE")
    start_review(session, case.id, actor=person("alice"))
    approve_review(session, case.id, actor=person("alice"))

    with pytest.raises(ReviewConflictError):
        reject_review(session, case.id, actor=person("alice"), reason="changed mind")


def test_cancel_from_open_and_in_review(session: Session) -> None:
    open_case = finding_case(session, supplier_code="SUP-CAN1")
    cancel_review(session, open_case.id, actor=person("alice"))
    assert get_case(session, open_case.id).status == ReviewStatus.cancelled.value

    active = finding_case(session, supplier_code="SUP-CAN2")
    start_review(session, active.id, actor=person("alice"))
    cancel_review(session, active.id, actor=person("alice"), comment="duplicate")
    assert get_case(session, active.id).status == ReviewStatus.cancelled.value


def test_an_actor_without_an_identity_cannot_be_built() -> None:
    """A transition is only reachable with a named subject, so the guard sits
    on the identity itself rather than on each workflow entry point."""

    with pytest.raises(InvalidTokenError):
        Principal(subject="  ", display_name="nobody", email=None, roles=frozenset())
    with pytest.raises(InvalidTokenError):
        Principal(subject="s-1", display_name="  ", email=None, roles=frozenset())


def test_opened_and_decided_timestamps_can_be_set(session: Session) -> None:
    case = finding_case(session, supplier_code="SUP-TIME")
    opened = datetime(2026, 8, 30, 10, 0, tzinfo=UTC)
    decided = opened + timedelta(hours=2)
    start_review(session, case.id, actor=person("alice"), occurred_at=opened)
    approve_review(session, case.id, actor=person("alice"), occurred_at=decided)
    loaded = get_case(session, case.id)

    assert loaded.opened_at == opened
    assert loaded.decided_at == decided
