from pathlib import Path

from retailops_api.review.dataset import load_dataset
from retailops_api.review.evaluate import evaluate, write_evaluation
from retailops_api.review.mock import MockAIReviewer
from retailops_api.review.types import ReviewEligibility


def test_packaged_dataset_covers_the_four_case_families() -> None:
    dataset = load_dataset()
    kinds = {case.kind for case in dataset.cases}
    types = {case.review_type.value for case in dataset.cases if case.review_type}

    assert dataset.version == "v001"
    assert kinds == {"review", "routing"}
    assert types == {
        "category_suggestion",
        "supplier_summary",
        "reconciliation_explanation",
    }
    assert any(case.expected.eligibility is not None for case in dataset.cases)
    assert all(case.expected.to_dict() for case in dataset.cases)


def test_harness_scores_the_mock_against_the_packaged_dataset() -> None:
    dataset = load_dataset()
    report = evaluate(MockAIReviewer(dataset.fixtures()), dataset)
    by_id = {score.case_id: score for score in report.scores}

    assert report.reviewer == "mock"
    assert report.metrics.case_count == len(dataset.cases)
    assert report.metrics.schema_validity == 1.0
    assert report.metrics.classification_accuracy == 1.0
    assert report.metrics.recommended_action_accuracy == 1.0
    assert report.metrics.confidence_presence == 1.0
    assert report.metrics.provider_failure_rate > 0
    assert by_id["cat-malformed"].observed_outcome == "schema_error"
    assert by_id["cat-fail"].provider_failed
    assert by_id["route-auto"].routing is not None
    assert by_id["route-auto"].routing.eligibility is ReviewEligibility.auto_eligible
    assert by_id["route-high-risk"].routing is not None
    assert by_id["route-high-risk"].routing.eligibility is ReviewEligibility.human_required


def test_report_is_machine_readable(tmp_path: Path) -> None:
    dataset = load_dataset()
    report = evaluate(MockAIReviewer(dataset.fixtures()), dataset)
    write_evaluation(report, tmp_path)

    payload = (tmp_path / "evaluation.json").read_text(encoding="utf-8")
    markdown = (tmp_path / "evaluation.md").read_text(encoding="utf-8")

    assert '"schema_validity"' in payload
    assert '"classification_accuracy"' in payload
    assert '"provider_failure_rate"' in payload
    assert "Schema validity" in markdown
    assert "cat-001" in markdown
