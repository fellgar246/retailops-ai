"""Create and load review cases. Does not commit."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from retailops_api.dataset.contract import quantize_money
from retailops_api.domain.models import (
    DocumentFinding,
    GoodsReceipt,
    PurchaseOrder,
    ReconciliationException,
    SupplierDocument,
    SupplierInvoice,
)
from retailops_api.domain.models.review import (
    ReviewAISnapshot,
    ReviewCase,
    ReviewEventType,
    ReviewPriority,
    ReviewStatus,
    ReviewSubjectType,
)
from retailops_api.review.audit import append_event
from retailops_api.review.cases import (
    ReviewCaseView,
    ReviewNotFoundError,
    ReviewValidationError,
    as_confidence,
    derive_priority,
    reference_key,
    risk_from_severity,
)
from retailops_api.review.schemas import ReviewResult
from retailops_api.review.types import ReviewRequest, RiskLevel


def get_case(session: Session, case_id: int) -> ReviewCase:
    case = session.get(
        ReviewCase,
        case_id,
        options=(
            selectinload(ReviewCase.snapshots),
            selectinload(ReviewCase.decisions),
            selectinload(ReviewCase.audit_events),
        ),
    )
    if case is None:
        raise ReviewNotFoundError(f"review case {case_id} not found")
    return case


def case_view(case: ReviewCase) -> ReviewCaseView:
    return ReviewCaseView(
        id=case.id,
        subject_type=ReviewSubjectType(case.subject_type),
        document_finding_id=case.document_finding_id,
        reconciliation_exception_id=case.reconciliation_exception_id,
        supplier_id=case.supplier_id,
        priority=ReviewPriority(case.priority),
        risk=RiskLevel(case.risk),
        confidence=case.confidence,
        financial_impact=case.financial_impact,
        recommended_action=case.recommended_action,
        status=ReviewStatus(case.status),
        reviewer=case.reviewer,
        reviewer_verified=case.reviewer_subject is not None,
        opened_at=case.opened_at,
        decided_at=case.decided_at,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


def create_review_case(
    session: Session,
    *,
    finding: DocumentFinding | None = None,
    exception: ReconciliationException | None = None,
    result: ReviewResult | None = None,
    request: ReviewRequest | None = None,
    priority: ReviewPriority | None = None,
    actor: str = "system",
    occurred_at: datetime | None = None,
) -> ReviewCase:
    """Open a case for a finding or exception. Re-calling returns the existing row.

    An AI snapshot is written only when ``result`` is supplied and the case
    does not already have one. Existing snapshot bytes are never updated.
    """

    subject_type, subject_id, supplier_id, risk, impact = _subject(
        session, finding=finding, exception=exception
    )
    existing = _existing(session, subject_type, subject_id)
    if existing is not None:
        if result is not None and not existing.snapshots:
            _add_snapshot(
                session,
                existing,
                result=result,
                request=request,
                subject_type=subject_type,
                subject_id=subject_id,
            )
        return existing

    if result is not None:
        risk = result.risk
        confidence = as_confidence(result.confidence)
        recommended = result.recommended_action.value
    else:
        confidence = None
        recommended = None
    chosen_priority = priority or derive_priority(risk, impact)
    when = occurred_at or datetime.now(UTC)
    case = ReviewCase(
        subject_type=subject_type.value,
        document_finding_id=(
            subject_id if subject_type is ReviewSubjectType.document_finding else None
        ),
        reconciliation_exception_id=(
            subject_id if subject_type is ReviewSubjectType.reconciliation_exception else None
        ),
        supplier_id=supplier_id,
        priority=chosen_priority.value,
        risk=risk.value,
        confidence=confidence,
        financial_impact=quantize_money(impact),
        recommended_action=recommended,
        status=ReviewStatus.open.value,
        created_at=when,
        updated_at=when,
    )
    session.add(case)
    session.flush()
    if result is not None:
        _add_snapshot(
            session,
            case,
            result=result,
            request=request,
            subject_type=subject_type,
            subject_id=subject_id,
        )
    append_event(
        session,
        case,
        event_type=ReviewEventType.created,
        actor=actor,
        to_status=ReviewStatus.open,
        payload={"reference": reference_key(subject_type, subject_id)},
        occurred_at=when,
    )
    return case


def snapshot_for(case: ReviewCase) -> ReviewAISnapshot | None:
    if not case.snapshots:
        return None
    return min(case.snapshots, key=lambda item: item.id)


def input_hash(
    *,
    subject_type: ReviewSubjectType,
    subject_id: int,
    result: ReviewResult,
    request: ReviewRequest | None,
) -> str:
    if request is not None:
        payload: dict[str, Any] = request.to_dict()
    else:
        payload = {
            "subject_type": subject_type.value,
            "subject_id": subject_id,
            "prompt_id": result.prompt_id,
            "prompt_version": result.prompt_version,
            "review_type": result.review_type.value,
        }
    canonical = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _add_snapshot(
    session: Session,
    case: ReviewCase,
    *,
    result: ReviewResult,
    request: ReviewRequest | None,
    subject_type: ReviewSubjectType,
    subject_id: int,
) -> ReviewAISnapshot:
    snapshot = ReviewAISnapshot(
        review_case_id=case.id,
        provider=result.provider,
        model=result.model,
        prompt_id=result.prompt_id,
        prompt_version=result.prompt_version,
        original_output=result.model_dump(mode="json"),
        confidence=as_confidence(result.confidence),
        recommendation=result.recommended_action.value,
        input_hash=input_hash(
            subject_type=subject_type, subject_id=subject_id, result=result, request=request
        ),
        reference_key=reference_key(subject_type, subject_id),
    )
    case.snapshots.append(snapshot)
    session.flush()
    return snapshot


def _existing(
    session: Session, subject_type: ReviewSubjectType, subject_id: int
) -> ReviewCase | None:
    stmt = select(ReviewCase).options(
        selectinload(ReviewCase.snapshots),
        selectinload(ReviewCase.decisions),
        selectinload(ReviewCase.audit_events),
    )
    if subject_type is ReviewSubjectType.document_finding:
        stmt = stmt.where(ReviewCase.document_finding_id == subject_id)
    else:
        stmt = stmt.where(ReviewCase.reconciliation_exception_id == subject_id)
    return session.scalar(stmt)


def _subject(
    session: Session,
    *,
    finding: DocumentFinding | None,
    exception: ReconciliationException | None,
) -> tuple[ReviewSubjectType, int, int | None, RiskLevel, Decimal]:
    if finding is not None and exception is not None:
        raise ReviewValidationError("a case links to a finding or an exception, not both")
    if finding is not None:
        document = session.get(SupplierDocument, finding.document_id)
        if document is None:
            raise ReviewNotFoundError(f"document {finding.document_id} not found")
        return (
            ReviewSubjectType.document_finding,
            finding.id,
            document.supplier_id,
            risk_from_severity(finding.severity),
            Decimal("0.0000"),
        )
    if exception is not None:
        return (
            ReviewSubjectType.reconciliation_exception,
            exception.id,
            _supplier_for_exception(session, exception),
            risk_from_severity(exception.severity),
            exception.financial_impact,
        )
    raise ReviewValidationError("a finding or a reconciliation exception is required")


def _supplier_for_exception(session: Session, exception: ReconciliationException) -> int | None:
    if exception.supplier_invoice_id is not None:
        invoice = session.get(SupplierInvoice, exception.supplier_invoice_id)
        if invoice is not None:
            return invoice.supplier_id
    if exception.purchase_order_id is not None:
        order = session.get(PurchaseOrder, exception.purchase_order_id)
        if order is not None:
            return order.supplier_id
    if exception.goods_receipt_id is not None:
        receipt = session.get(GoodsReceipt, exception.goods_receipt_id)
        if receipt is not None:
            return receipt.supplier_id
    return None


def load_finding(session: Session, finding_id: int) -> DocumentFinding:
    finding = session.get(DocumentFinding, finding_id)
    if finding is None:
        raise ReviewNotFoundError(f"document finding {finding_id} not found")
    return finding


def load_exception(session: Session, exception_id: int) -> ReconciliationException:
    exception = session.get(ReconciliationException, exception_id)
    if exception is None:
        raise ReviewNotFoundError(f"reconciliation exception {exception_id} not found")
    return exception
