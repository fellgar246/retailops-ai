from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from retailops_api.api.deps import get_db
from retailops_api.domain.repositories import get_supplier_by_code
from retailops_api.review.audit import list_events
from retailops_api.review.cases import (
    ReviewConflictError,
    ReviewFilters,
    ReviewNotFoundError,
    ReviewPriority,
    ReviewStatus,
    ReviewSubjectType,
    ReviewValidationError,
)
from retailops_api.review.feedback import project_feedback
from retailops_api.review.metrics import collect_metrics
from retailops_api.review.persist import (
    case_view,
    create_review_case,
    get_case,
    load_exception,
    load_finding,
    snapshot_for,
)
from retailops_api.review.queue import DEFAULT_LIMIT, MAX_LIMIT, list_cases
from retailops_api.review.schemas import parse_review_result
from retailops_api.review.types import ReviewSchemaError, RiskLevel
from retailops_api.review.workflow import (
    approve_review,
    assign_review,
    cancel_review,
    correct_review,
    reject_review,
    start_review,
)

router = APIRouter(prefix="/reviews", tags=["reviews"])
DbSession = Annotated[Session, Depends(get_db)]


class CreateReviewBody(BaseModel):
    document_finding_id: int | None = None
    reconciliation_exception_id: int | None = None
    priority: ReviewPriority | None = None
    ai_result: dict[str, Any] | None = None


class ReviewerBody(BaseModel):
    reviewer: str = Field(min_length=1, max_length=128)


class ApproveBody(ReviewerBody):
    comment: str | None = None
    snapshot_id: int | None = None


class RejectBody(ReviewerBody):
    reason: str = Field(min_length=1)
    comment: str | None = None


class CorrectBody(ReviewerBody):
    correction: dict[str, Any]
    comment: str | None = None


class CancelBody(ReviewerBody):
    comment: str | None = None


@router.get("/metrics")
def review_metrics(session: DbSession) -> dict[str, Any]:
    return collect_metrics(session).to_dict()


@router.get("/feedback")
def review_feedback(session: DbSession) -> dict[str, Any]:
    rows = project_feedback(session)
    return {"items": [row.to_dict() for row in rows], "count": len(rows)}


@router.get("")
def review_queue(
    session: DbSession,
    status: Annotated[list[ReviewStatus] | None, Query()] = None,
    priority: Annotated[list[ReviewPriority] | None, Query()] = None,
    subject_type: Annotated[list[ReviewSubjectType] | None, Query()] = None,
    risk: Annotated[list[RiskLevel] | None, Query()] = None,
    supplier_id: int | None = None,
    supplier: str | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> dict[str, Any]:
    if limit < 1 or limit > MAX_LIMIT:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 200")
    if offset < 0:
        raise HTTPException(status_code=400, detail="offset must be at least 0")
    resolved_supplier = supplier_id
    if supplier is not None:
        row = get_supplier_by_code(session, supplier)
        if row is None:
            raise HTTPException(status_code=404, detail=f"supplier {supplier} not found")
        resolved_supplier = row.id
    page = list_cases(
        session,
        ReviewFilters(
            statuses=tuple(status or ()),
            priorities=tuple(priority or ()),
            subject_types=tuple(subject_type or ()),
            supplier_id=resolved_supplier,
            risks=tuple(risk or ()),
            created_from=created_from,
            created_to=created_to,
        ),
        limit=limit,
        offset=offset,
    )
    return page.to_dict()


@router.post("", status_code=201)
def create_review(body: CreateReviewBody, session: DbSession) -> dict[str, Any]:
    return _translate(lambda: _create(session, body))


@router.get("/{case_id}")
def get_review(case_id: int, session: DbSession) -> dict[str, Any]:
    return _translate(lambda: _detail(session, case_id))


@router.get("/{case_id}/audit")
def get_review_audit(case_id: int, session: DbSession) -> dict[str, Any]:
    return _translate(lambda: _audit(session, case_id))


@router.post("/{case_id}/start")
def start_case(case_id: int, body: ReviewerBody, session: DbSession) -> dict[str, Any]:
    return _translate(
        lambda: case_view(start_review(session, case_id, reviewer=body.reviewer)).to_dict()
    )


@router.post("/{case_id}/assign")
def assign_case(case_id: int, body: ReviewerBody, session: DbSession) -> dict[str, Any]:
    return _translate(
        lambda: case_view(assign_review(session, case_id, reviewer=body.reviewer)).to_dict()
    )


@router.post("/{case_id}/approve")
def approve_case(case_id: int, body: ApproveBody, session: DbSession) -> dict[str, Any]:
    return _translate(
        lambda: case_view(
            approve_review(
                session,
                case_id,
                reviewer=body.reviewer,
                comment=body.comment,
                snapshot_id=body.snapshot_id,
            )
        ).to_dict()
    )


@router.post("/{case_id}/reject")
def reject_case(case_id: int, body: RejectBody, session: DbSession) -> dict[str, Any]:
    return _translate(
        lambda: case_view(
            reject_review(
                session, case_id, reviewer=body.reviewer, reason=body.reason, comment=body.comment
            )
        ).to_dict()
    )


@router.post("/{case_id}/correct")
def correct_case(case_id: int, body: CorrectBody, session: DbSession) -> dict[str, Any]:
    return _translate(
        lambda: case_view(
            correct_review(
                session,
                case_id,
                reviewer=body.reviewer,
                correction=body.correction,
                comment=body.comment,
            )
        ).to_dict()
    )


@router.post("/{case_id}/cancel")
def cancel_case(case_id: int, body: CancelBody, session: DbSession) -> dict[str, Any]:
    return _translate(
        lambda: case_view(
            cancel_review(session, case_id, reviewer=body.reviewer, comment=body.comment)
        ).to_dict()
    )


def _create(session: Session, body: CreateReviewBody) -> dict[str, Any]:
    finding = (
        None
        if body.document_finding_id is None
        else load_finding(session, body.document_finding_id)
    )
    exception = (
        None
        if body.reconciliation_exception_id is None
        else load_exception(session, body.reconciliation_exception_id)
    )
    result = None if body.ai_result is None else parse_review_result(body.ai_result)
    case = create_review_case(
        session,
        finding=finding,
        exception=exception,
        result=result,
        priority=body.priority,
    )
    return _detail(session, case.id)


def _detail(session: Session, case_id: int) -> dict[str, Any]:
    case = get_case(session, case_id)
    snapshot = snapshot_for(case)
    decision = min(case.decisions, key=lambda item: item.id) if case.decisions else None
    payload = case_view(case).to_dict()
    payload["snapshot"] = None
    if snapshot is not None:
        payload["snapshot"] = {
            "id": snapshot.id,
            "provider": snapshot.provider,
            "model": snapshot.model,
            "prompt_id": snapshot.prompt_id,
            "prompt_version": snapshot.prompt_version,
            "confidence": str(snapshot.confidence),
            "recommendation": snapshot.recommendation,
            "input_hash": snapshot.input_hash,
            "reference_key": snapshot.reference_key,
            "original_output": snapshot.original_output,
        }
    payload["decision"] = None
    if decision is not None:
        payload["decision"] = {
            "id": decision.id,
            "decision": decision.decision,
            "reviewer": decision.reviewer,
            "reason": decision.reason,
            "comment": decision.comment,
            "accepted_recommendation_ref": decision.accepted_recommendation_ref,
            "correction": decision.correction,
            "created_at": decision.created_at.isoformat(),
        }
    return payload


def _audit(session: Session, case_id: int) -> dict[str, Any]:
    get_case(session, case_id)
    events = list_events(session, case_id)
    return {
        "items": [
            {
                "id": event.id,
                "event_type": event.event_type,
                "actor": event.actor,
                "from_status": event.from_status,
                "to_status": event.to_status,
                "payload": event.payload,
                "created_at": event.created_at.isoformat(),
            }
            for event in events
        ]
    }


def _translate(action: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    try:
        return action()
    except ReviewNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ReviewConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except (ReviewValidationError, ReviewSchemaError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
