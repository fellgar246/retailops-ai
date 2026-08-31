import json

import pytest

from retailops_api.review.bedrock import (
    BedrockAIReviewer,
    BedrockErrorClass,
    RetryPolicy,
    build_bedrock_request,
    classify_bedrock_error,
    parse_bedrock_response,
)
from retailops_api.review.contract import build_request
from retailops_api.review.mock import canned_output
from retailops_api.review.types import (
    CategorySuggestionInput,
    ReviewerError,
    ReviewRequest,
    ReviewSchemaError,
    ReviewType,
)
from tests.aws_fakes import FakeBedrock, FakeClientError


def _request() -> ReviewRequest:
    return build_request(
        ReviewType.category_suggestion,
        CategorySuggestionInput(
            submitted_category="soft drinks",
            description="cola",
            catalog_codes=("BEV-SOFT",),
            catalog_names=("Soft drinks",),
            findings=(),
        ),
        case_id="case-1",
    )


def test_bedrock_builds_a_structured_request() -> None:
    request = _request()
    built = build_bedrock_request(
        request,
        model_id="anthropic.claude-test",
        template="Return the structured review result only.",
    )
    assert built.model_id == "anthropic.claude-test"
    assert built.body["anthropic_version"] == "bedrock-2023-05-31"
    user = json.loads(built.body["messages"][0]["content"])
    assert user["request"]["review_type"] == "category_suggestion"
    assert "instructions" in user


def test_bedrock_review_parses_and_stamps_provider_metadata() -> None:
    request = _request()
    payload = canned_output(ReviewType.category_suggestion)
    reviewer = BedrockAIReviewer(
        FakeBedrock(payload),
        model_id="anthropic.claude-test",
        sleep=lambda _: None,
    )
    result = reviewer.review(request)
    assert result.provider == "bedrock"
    assert result.model == "anthropic.claude-test"
    assert result.prompt_id == request.prompt_id
    assert result.suggested_value == "BEV-SOFT"


def test_bedrock_rejects_malformed_output() -> None:
    request = _request()
    reviewer = BedrockAIReviewer(
        FakeBedrock({"summary": 1}),
        model_id="anthropic.claude-test",
        sleep=lambda _: None,
    )
    with pytest.raises(ReviewSchemaError):
        reviewer.review(request)


def test_bedrock_retries_throttling_then_succeeds() -> None:
    request = _request()
    payload = canned_output(ReviewType.category_suggestion)
    client = FakeBedrock(
        payload,
        fail_times=2,
        fail_error=FakeClientError("ThrottlingException"),
    )
    reviewer = BedrockAIReviewer(
        client,
        model_id="anthropic.claude-test",
        retry=RetryPolicy(max_attempts=3, base_delay_seconds=0),
        sleep=lambda _: None,
    )
    result = reviewer.review(request)
    assert result.provider == "bedrock"
    assert len(client.calls) == 3


def test_bedrock_does_not_retry_access_denied() -> None:
    request = _request()
    client = FakeBedrock(error=FakeClientError("AccessDeniedException"))
    reviewer = BedrockAIReviewer(
        client,
        model_id="anthropic.claude-test",
        retry=RetryPolicy(max_attempts=3, base_delay_seconds=0),
        sleep=lambda _: None,
    )
    with pytest.raises(ReviewerError, match="access_denied"):
        reviewer.review(request)
    assert len(client.calls) == 1


def test_classify_bedrock_error_codes() -> None:
    throttled = classify_bedrock_error(FakeClientError("ThrottlingException"))
    validation = classify_bedrock_error(FakeClientError("ValidationException"))
    assert throttled is BedrockErrorClass.throttled
    assert validation is BedrockErrorClass.validation
    assert classify_bedrock_error(FakeClientError("ServiceUnavailableException")) is (
        BedrockErrorClass.unavailable
    )


def test_parse_bedrock_response_accepts_raw_review_object() -> None:
    payload = canned_output(ReviewType.category_suggestion)
    parsed = parse_bedrock_response({"body": json.dumps(payload)})
    assert isinstance(parsed, dict)
    assert parsed["review_type"] == "category_suggestion"
