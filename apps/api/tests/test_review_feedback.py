"""Feedback projection for evaluation rows."""

from pathlib import Path

from sqlalchemy.orm import Session

from retailops_api.review.feedback import FEEDBACK_JSONL, project_feedback, write_feedback
from retailops_api.review.workflow import approve_review, correct_review, start_review
from tests.review_support import finding_case, person


def test_feedback_exports_decided_cases_with_ai_and_correction(
    session: Session, tmp_path: Path
) -> None:
    approved = finding_case(session, supplier_code="SUP-FB1")
    start_review(session, approved.id, actor=person("alice"))
    approve_review(session, approved.id, actor=person("alice"))

    corrected = finding_case(session, supplier_code="SUP-FB2", suggested_value="BEV-SOFT")
    start_review(session, corrected.id, actor=person("alice"))
    correct_review(
        session,
        corrected.id,
        actor=person("alice"),
        correction={"suggested_value": "BEV-WATER"},
    )
    finding_case(session, supplier_code="SUP-FB3")

    rows = project_feedback(session)
    assert [row.review_case_id for row in rows] == [approved.id, corrected.id]
    by_id = {row.review_case_id: row for row in rows}
    assert by_id[approved.id].decision == "approved"
    assert by_id[approved.id].ai_result is not None
    assert by_id[approved.id].prompt_id
    assert by_id[approved.id].model
    assert by_id[approved.id].input_hash
    assert by_id[approved.id].input_reference.startswith("document_finding:")
    assert by_id[corrected.id].decision == "corrected"
    correction = by_id[corrected.id].correction
    assert correction is not None
    assert correction["suggested_value"] == "BEV-WATER"
    ai_result = by_id[corrected.id].ai_result
    assert ai_result is not None
    assert ai_result["suggested_value"] == "BEV-SOFT"

    path = write_feedback(rows, tmp_path)
    assert path == tmp_path / FEEDBACK_JSONL
    assert path.read_text(encoding="utf-8").count("\n") == 2
