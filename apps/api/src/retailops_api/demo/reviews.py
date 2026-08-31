"""Open human-review cases with the mock reviewer for demo findings and exceptions."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from retailops_api.documents.types import ProcessResult
from retailops_api.domain.models import DocumentFinding, ReconciliationException, ReviewCase
from retailops_api.procurement.types import ReconciliationResult
from retailops_api.review.mock import MockAIReviewer, canned_output
from retailops_api.review.persist import create_review_case
from retailops_api.review.reconciliation import explain_exception
from retailops_api.review.schemas import parse_review_result
from retailops_api.review.supplier import review_from_process_result
from retailops_api.review.types import ReviewType


def open_demo_reviews(
    session: Session,
    documents: list[ProcessResult],
    reconciliations: list[ReconciliationResult],
) -> list[ReviewCase]:
    """Attach mock-AI snapshots and open a case for each material finding or exception."""

    reviewer = MockAIReviewer()
    cases: list[ReviewCase] = []
    cases.extend(_cases_for_documents(session, documents, reviewer))
    cases.extend(_cases_for_reconciliations(session, reconciliations, reviewer))
    session.flush()
    return cases


def _cases_for_documents(
    session: Session,
    documents: list[ProcessResult],
    reviewer: MockAIReviewer,
) -> list[ReviewCase]:
    cases: list[ReviewCase] = []
    for document in documents:
        semantic = review_from_process_result(document, reviewer)
        findings = session.scalars(
            select(DocumentFinding).where(DocumentFinding.document_id == document.document_id)
        ).all()
        fallback = parse_review_result(canned_output(ReviewType.supplier_summary))
        result = semantic.ai_result or fallback
        for finding in findings:
            if finding.severity == "info":
                continue
            cases.append(create_review_case(session, finding=finding, result=result, actor="demo"))
    return cases


def _cases_for_reconciliations(
    session: Session,
    reconciliations: list[ReconciliationResult],
    reviewer: MockAIReviewer,
) -> list[ReviewCase]:
    cases: list[ReviewCase] = []
    for run in reconciliations:
        persisted = session.scalars(
            select(ReconciliationException).where(
                ReconciliationException.reconciliation_run_id == run.run_id
            )
        ).all()
        by_code = {item.code: item for item in persisted}
        for proposed in run.exceptions:
            row = by_code.get(proposed.code)
            if row is None:
                continue
            explanation = explain_exception(proposed, reviewer, case_id=f"{run.scope_key}:{row.id}")
            result = explanation.ai_result or parse_review_result(
                canned_output(ReviewType.reconciliation_explanation)
            )
            cases.append(create_review_case(session, exception=row, result=result, actor="demo"))
    return cases
