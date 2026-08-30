"""Queue filters, stable ordering and pagination."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from retailops_api.review.cases import (
    ReviewFilters,
    ReviewPriority,
    ReviewStatus,
    ReviewSubjectType,
)
from retailops_api.review.persist import create_review_case
from retailops_api.review.queue import list_cases
from retailops_api.review.types import RiskLevel
from tests.factories import make_document_finding, make_supplier, make_supplier_document
from tests.review_support import exception_case, finding_case


def test_queue_orders_by_priority_then_created_then_id(session: Session) -> None:
    early = datetime(2026, 8, 1, tzinfo=UTC)
    later = datetime(2026, 8, 2, tzinfo=UTC)
    low = finding_case(session, supplier_code="SUP-Q1")
    low.priority = ReviewPriority.low.value
    low.created_at = later
    high_old = finding_case(session, supplier_code="SUP-Q2")
    high_old.priority = ReviewPriority.high.value
    high_old.created_at = early
    high_new = finding_case(session, supplier_code="SUP-Q3")
    high_new.priority = ReviewPriority.high.value
    high_new.created_at = later
    session.flush()

    page = list_cases(session)
    assert [item.id for item in page.items] == [high_old.id, high_new.id, low.id]


def test_queue_filters_status_priority_subject_supplier_risk_and_date(session: Session) -> None:
    finding = finding_case(session, supplier_code="SUP-QF1", risk="high")
    finding.status = ReviewStatus.in_review.value
    finding.priority = ReviewPriority.urgent.value
    finding.risk = RiskLevel.high.value
    finding.created_at = datetime(2026, 8, 15, tzinfo=UTC)
    other = finding_case(session, supplier_code="SUP-QF2")
    other.created_at = datetime(2026, 7, 1, tzinfo=UTC)
    exception_case(session, supplier_code="SUP-QF3")
    session.flush()

    page = list_cases(
        session,
        ReviewFilters(
            statuses=(ReviewStatus.in_review,),
            priorities=(ReviewPriority.urgent,),
            subject_types=(ReviewSubjectType.document_finding,),
            supplier_id=finding.supplier_id,
            risks=(RiskLevel.high,),
            created_from=datetime(2026, 8, 1, tzinfo=UTC).date(),
            created_to=datetime(2026, 8, 31, tzinfo=UTC).date(),
        ),
    )
    assert page.total == 1
    assert page.items[0].id == finding.id


def test_pagination_is_stable(session: Session) -> None:
    ids = []
    for index in range(3):
        case = finding_case(session, supplier_code=f"SUP-PG{index}")
        case.priority = ReviewPriority.medium.value
        ids.append(case.id)
    session.flush()

    first = list_cases(session, limit=2, offset=0)
    second = list_cases(session, limit=2, offset=2)
    assert first.total == 3
    assert len(first.items) == 2
    assert len(second.items) == 1
    assert {item.id for item in first.items} | {item.id for item in second.items} == set(ids)


def test_create_without_ai_result_still_queues(session: Session) -> None:
    supplier = make_supplier(session, code="SUP-NOAI")
    document = make_supplier_document(session, supplier, storage_key="n" * 32)
    finding = make_document_finding(session, document)
    case = create_review_case(session, finding=finding)
    page = list_cases(session, ReviewFilters(statuses=(ReviewStatus.open,)))

    assert case.confidence is None
    assert page.total == 1
    assert page.items[0].id == case.id
