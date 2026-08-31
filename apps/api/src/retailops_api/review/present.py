"""API-facing review payloads with supplier and subject context."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from retailops_api.documents.query import finding_dict
from retailops_api.domain.models import (
    DocumentFinding,
    ReconciliationException,
    Supplier,
    SupplierDocument,
)
from retailops_api.procurement.query import exception_dict
from retailops_api.review.cases import ReviewCaseView, ReviewSubjectType


def case_payload(session: Session, view: ReviewCaseView) -> dict[str, Any]:
    payload = view.to_dict()
    supplier = None if view.supplier_id is None else session.get(Supplier, view.supplier_id)
    payload["supplier_code"] = None if supplier is None else supplier.code
    payload["supplier_name"] = None if supplier is None else supplier.name
    payload["subject_summary"] = _subject_summary(session, view)
    return payload


def subject_payload(session: Session, view: ReviewCaseView) -> dict[str, Any]:
    if view.subject_type is ReviewSubjectType.document_finding and view.document_finding_id:
        finding = session.get(DocumentFinding, view.document_finding_id)
        document = None if finding is None else session.get(SupplierDocument, finding.document_id)
        return {
            "type": view.subject_type.value,
            "finding": None if finding is None else finding_dict(finding),
            "document": None
            if document is None
            else {
                "id": document.id,
                "filename": document.filename,
                "status": document.status,
            },
            "exception": None,
        }
    exception = (
        None
        if view.reconciliation_exception_id is None
        else session.get(ReconciliationException, view.reconciliation_exception_id)
    )
    return {
        "type": view.subject_type.value,
        "finding": None,
        "document": None,
        "exception": None if exception is None else exception_dict(exception),
    }


def _subject_summary(session: Session, view: ReviewCaseView) -> str | None:
    if view.document_finding_id is not None:
        finding = session.get(DocumentFinding, view.document_finding_id)
        return None if finding is None else finding.message
    if view.reconciliation_exception_id is not None:
        exception = session.get(ReconciliationException, view.reconciliation_exception_id)
        return None if exception is None else exception.message
    return None


def page_payload(
    session: Session, items: tuple[ReviewCaseView, ...], total: int, limit: int, offset: int
) -> dict[str, Any]:
    return {
        "items": [case_payload(session, item) for item in items],
        "total": total,
        "limit": limit,
        "offset": offset,
    }
