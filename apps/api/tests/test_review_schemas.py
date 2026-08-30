import pytest

from retailops_api.review.mock import canned_output
from retailops_api.review.schemas import parse_review_result
from retailops_api.review.types import ReviewSchemaError, ReviewType


def test_valid_payload_parses() -> None:
    result = parse_review_result(canned_output(ReviewType.category_suggestion))

    assert result.review_type is ReviewType.category_suggestion
    assert 0 <= result.confidence <= 1
    assert result.output_schema_version == "1"


def test_json_string_parses() -> None:
    result = parse_review_result(
        '{"review_type":"supplier_summary","summary":"ok","findings":[],'
        '"reasoning_summary":"n","confidence":0.5,"risk":"low",'
        '"recommended_action":"human_review","provider":"x","model":"y",'
        '"prompt_id":"supplier.summary","prompt_version":"1",'
        '"input_schema_version":"1","output_schema_version":"1"}'
    )

    assert result.summary == "ok"


def test_missing_confidence_is_malformed() -> None:
    payload = canned_output(ReviewType.category_suggestion)
    del payload["confidence"]

    with pytest.raises(ReviewSchemaError, match="malformed"):
        parse_review_result(payload)


def test_confidence_outside_unit_interval_is_malformed() -> None:
    payload = canned_output(ReviewType.category_suggestion, confidence=1.2)

    with pytest.raises(ReviewSchemaError, match="malformed"):
        parse_review_result(payload)


def test_unknown_action_is_malformed() -> None:
    payload = canned_output(ReviewType.supplier_summary, recommended_action="invent")

    with pytest.raises(ReviewSchemaError, match="malformed"):
        parse_review_result(payload)


def test_non_object_payload_is_malformed() -> None:
    with pytest.raises(ReviewSchemaError):
        parse_review_result(["not", "an", "object"])


def test_invalid_json_is_malformed() -> None:
    with pytest.raises(ReviewSchemaError):
        parse_review_result("{")
