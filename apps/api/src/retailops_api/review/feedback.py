"""Project decided reviews into evaluation-friendly rows."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from retailops_api.domain.models.review import (
    ReviewAISnapshot,
    ReviewCase,
    ReviewDecisionRecord,
    ReviewStatus,
)
from retailops_api.review.persist import snapshot_for

FEEDBACK_JSONL = "feedback.jsonl"

_DECIDED = (
    ReviewStatus.approved.value,
    ReviewStatus.rejected.value,
    ReviewStatus.corrected.value,
)


@dataclass(frozen=True)
class FeedbackRow:
    review_case_id: int
    input_reference: str
    input_hash: str | None
    subject_type: str
    ai_result: dict[str, Any] | None
    confidence: str | None
    decision: str
    correction: dict[str, Any] | None
    prompt_id: str | None
    prompt_version: str | None
    provider: str | None
    model: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "review_case_id": self.review_case_id,
            "input_reference": self.input_reference,
            "input_hash": self.input_hash,
            "subject_type": self.subject_type,
            "ai_result": self.ai_result,
            "confidence": self.confidence,
            "decision": self.decision,
            "correction": self.correction,
            "prompt_id": self.prompt_id,
            "prompt_version": self.prompt_version,
            "provider": self.provider,
            "model": self.model,
        }


def project_feedback(session: Session) -> tuple[FeedbackRow, ...]:
    cases = session.scalars(
        select(ReviewCase)
        .options(
            selectinload(ReviewCase.snapshots),
            selectinload(ReviewCase.decisions),
        )
        .where(ReviewCase.status.in_(_DECIDED))
        .order_by(ReviewCase.id.asc())
    ).all()
    return tuple(_row(case) for case in cases if case.decisions)


def write_feedback(rows: tuple[FeedbackRow, ...], directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / FEEDBACK_JSONL
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row.to_dict(), sort_keys=True, default=str))
            handle.write("\n")
    return path


def _row(case: ReviewCase) -> FeedbackRow:
    decision = min(case.decisions, key=lambda item: item.id)
    snapshot = snapshot_for(case)
    return FeedbackRow(
        review_case_id=case.id,
        input_reference=_reference(case, snapshot),
        input_hash=None if snapshot is None else snapshot.input_hash,
        subject_type=case.subject_type,
        ai_result=None if snapshot is None else dict(snapshot.original_output),
        confidence=_confidence(case, snapshot),
        decision=decision.decision,
        correction=decision.correction,
        prompt_id=None if snapshot is None else snapshot.prompt_id,
        prompt_version=None if snapshot is None else snapshot.prompt_version,
        provider=None if snapshot is None else snapshot.provider,
        model=None if snapshot is None else snapshot.model,
    )


def _reference(case: ReviewCase, snapshot: ReviewAISnapshot | None) -> str:
    if snapshot is not None:
        return snapshot.reference_key
    if case.document_finding_id is not None:
        return f"document_finding:{case.document_finding_id}"
    return f"reconciliation_exception:{case.reconciliation_exception_id}"


def _confidence(case: ReviewCase, snapshot: ReviewAISnapshot | None) -> str | None:
    if snapshot is not None:
        return str(snapshot.confidence)
    if case.confidence is None:
        return None
    return str(case.confidence)


def latest_decision(case: ReviewCase) -> ReviewDecisionRecord | None:
    if not case.decisions:
        return None
    return min(case.decisions, key=lambda item: item.id)
