import pytest

from retailops_api.review.contract import build_request, review_safely
from retailops_api.review.mock import MockAIReviewer, MockBehavior, MockFixture, canned_output
from retailops_api.review.types import (
    CategorySuggestionInput,
    ReviewerError,
    ReviewRequest,
    ReviewSchemaError,
    ReviewType,
)


def _request(case_id: str | None = None) -> ReviewRequest:
    return build_request(
        ReviewType.category_suggestion,
        CategorySuggestionInput(
            submitted_category="refrescos",
            description="Cola",
            catalog_codes=("BEV-SOFT",),
            catalog_names=("Soft drinks",),
            findings=(),
        ),
        case_id=case_id,
    )


def test_normal_fixture_returns_validated_result() -> None:
    reviewer = MockAIReviewer()
    result = reviewer.review(_request())

    assert result.provider == "mock"
    assert result.confidence >= 0.85
    assert result.suggested_value == "BEV-SOFT"


def test_low_confidence_fixture() -> None:
    reviewer = MockAIReviewer(default_behavior=MockBehavior.low_confidence)
    result = reviewer.review(_request())

    assert result.confidence < 0.5


def test_malformed_fixture_fails_schema() -> None:
    reviewer = MockAIReviewer(default_behavior=MockBehavior.malformed)

    with pytest.raises(ReviewSchemaError):
        reviewer.review(_request())


def test_provider_failure_raises() -> None:
    reviewer = MockAIReviewer(default_behavior=MockBehavior.provider_failure)

    with pytest.raises(ReviewerError, match="provider failure"):
        reviewer.review(_request())


def test_case_id_selects_a_fixture() -> None:
    reviewer = MockAIReviewer(
        {
            "case-a": MockFixture(
                behavior=MockBehavior.normal,
                output=canned_output(
                    ReviewType.category_suggestion,
                    suggested_value="BEV-WATER",
                ),
            )
        }
    )
    result = reviewer.review(_request("case-a"))

    assert result.suggested_value == "BEV-WATER"


def test_safe_review_does_not_surface_malformed_output() -> None:
    reviewer = MockAIReviewer(default_behavior=MockBehavior.malformed)
    attempt = review_safely(reviewer, _request())

    assert not attempt.ok
    assert attempt.result is None
    assert attempt.schema_failed
