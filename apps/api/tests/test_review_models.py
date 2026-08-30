"""Review case, snapshot, decision and audit persistence constraints."""

from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from retailops_api.domain.models import ReviewAISnapshot, ReviewAuditEvent, ReviewCase
from retailops_api.domain.models.review import ReviewEventType, ReviewStatus
from retailops_api.review.persist import create_review_case, snapshot_for
from tests.factories import (
    make_document_finding,
    make_reconciliation_exception,
    make_review_case,
    make_supplier,
    make_supplier_document,
)
from tests.review_support import finding_case


def test_a_case_links_to_a_finding_and_starts_open(session: Session) -> None:
    case = finding_case(session)

    assert case.status == ReviewStatus.open.value
    assert case.document_finding_id is not None
    assert case.reconciliation_exception_id is None
    assert case.confidence is not None
    assert case.created_at is not None
    assert case.updated_at is not None
    assert case.active is True


def test_creating_the_same_subject_twice_returns_the_existing_case(session: Session) -> None:
    first = finding_case(session, supplier_code="SUP-DUP")
    supplier = first.supplier
    assert supplier is not None
    finding = first.document_finding
    assert finding is not None
    second = create_review_case(session, finding=finding)

    assert second.id == first.id
    assert session.scalar(select(ReviewCase).where(ReviewCase.id == first.id)) is not None
    assert len(session.scalars(select(ReviewCase)).all()) == 1


def test_ai_snapshot_is_immutable_on_recreate(session: Session) -> None:
    case = finding_case(session, supplier_code="SUP-SNAP", suggested_value="BEV-SOFT")
    original = snapshot_for(case)
    assert original is not None
    first_output = dict(original.original_output)

    finding = case.document_finding
    assert finding is not None
    from retailops_api.review.mock import canned_output
    from retailops_api.review.schemas import parse_review_result
    from retailops_api.review.types import ReviewType

    create_review_case(
        session,
        finding=finding,
        result=parse_review_result(
            canned_output(ReviewType.category_suggestion, suggested_value="BEV-WATER")
        ),
    )
    session.refresh(original)

    assert original.original_output == first_output
    assert original.original_output["suggested_value"] == "BEV-SOFT"
    assert len(case.snapshots) == 1


def test_a_case_cannot_point_at_both_subjects(session: Session) -> None:
    supplier = make_supplier(session)
    document = make_supplier_document(session, supplier)
    finding = make_document_finding(session, document)
    exception = make_reconciliation_exception(session)

    with pytest.raises(IntegrityError):
        session.add(
            ReviewCase(
                subject_type="document_finding",
                document_finding_id=finding.id,
                reconciliation_exception_id=exception.id,
                supplier_id=supplier.id,
                priority="low",
                risk="low",
                financial_impact=Decimal("0"),
                status=ReviewStatus.open.value,
            )
        )
        session.flush()


def test_unknown_status_is_rejected(session: Session) -> None:
    supplier = make_supplier(session)
    document = make_supplier_document(session, supplier)
    finding = make_document_finding(session, document)

    with pytest.raises(IntegrityError):
        make_review_case(session, finding=finding, supplier=supplier, status="invented")


def test_audit_events_are_not_overwritten(session: Session) -> None:
    case = finding_case(session, supplier_code="SUP-AUD")
    first = session.scalars(select(ReviewAuditEvent).order_by(ReviewAuditEvent.id)).all()
    assert [event.event_type for event in first] == [ReviewEventType.created.value]

    from retailops_api.review.audit import append_event
    from retailops_api.review.cases import ReviewEventType as Event

    append_event(session, case, event_type=Event.opened, actor="alice")
    events = session.scalars(select(ReviewAuditEvent).order_by(ReviewAuditEvent.id)).all()
    assert [event.event_type for event in events] == [
        ReviewEventType.created.value,
        ReviewEventType.opened.value,
    ]
    assert events[0].id != events[1].id


def test_snapshot_carries_provider_prompt_and_hash(session: Session) -> None:
    case = finding_case(session, supplier_code="SUP-HASH")
    snapshot = snapshot_for(case)
    assert snapshot is not None
    assert snapshot.provider
    assert snapshot.model
    assert snapshot.prompt_id
    assert snapshot.prompt_version
    assert len(snapshot.input_hash) == 64
    assert snapshot.reference_key.startswith("document_finding:")
    assert session.get(ReviewAISnapshot, snapshot.id) is not None
