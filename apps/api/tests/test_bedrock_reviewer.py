import json

import pytest

from retailops_api.core.retry import RetryPolicy
from retailops_api.review.bedrock import (
    BedrockAIReviewer,
    BedrockErrorClass,
    build_bedrock_request,
    classify_bedrock_error,
    parse_bedrock_response,
)
from retailops_api.review.contract import build_request
from retailops_api.review.mock import canned_output
from retailops_api.review.output_schema import REVIEW_RESULT_TOOL_NAME
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


def test_bedrock_builds_a_converse_request() -> None:
    request = _request()
    built = build_bedrock_request(
        request,
        model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0",
        template="Return the structured review result only.",
        max_tokens=512,
        temperature=0.0,
    )
    assert built.model_id == "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    assert "anthropic_version" not in built.inference_config
    assert built.inference_config["maxTokens"] == 512
    assert built.inference_config["temperature"] == 0.0
    assert built.tool_config["toolChoice"]["tool"]["name"] == REVIEW_RESULT_TOOL_NAME
    user = json.loads(built.messages[0]["content"][0]["text"])
    assert user["request"]["review_type"] == "category_suggestion"
    assert "instructions" in user


def test_bedrock_rejects_oversized_prompts() -> None:
    request = _request()
    with pytest.raises(ReviewerError, match="max payload"):
        build_bedrock_request(
            request,
            model_id="anthropic.claude-test",
            template="x",
            max_prompt_chars=8,
        )


def test_bedrock_review_parses_and_stamps_provider_metadata() -> None:
    request = _request()
    payload = canned_output(ReviewType.category_suggestion)
    payload.pop("input_schema_version")
    payload.pop("output_schema_version")
    reviewer = BedrockAIReviewer(
        FakeBedrock(payload),
        model_id="anthropic.claude-test",
        sleep=lambda _: None,
    )
    result = reviewer.review(request)
    assert result.provider == "bedrock"
    assert result.model == "anthropic.claude-test"
    assert result.prompt_id == request.prompt_id
    assert result.input_schema_version == "1"
    assert result.output_schema_version == "1"
    assert result.suggested_value == "BEV-SOFT"
    assert reviewer.last_usage is not None
    assert reviewer.last_usage.input_tokens == 12


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
    assert "modelId" in client.calls[-1]


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


def test_bedrock_retries_timeouts() -> None:
    request = _request()
    client = FakeBedrock(
        canned_output(ReviewType.category_suggestion),
        fail_times=1,
        fail_error=FakeClientError("ReadTimeoutError"),
    )
    reviewer = BedrockAIReviewer(
        client,
        model_id="anthropic.claude-test",
        retry=RetryPolicy(max_attempts=2, base_delay_seconds=0),
        sleep=lambda _: None,
    )
    reviewer.review(request)
    assert len(client.calls) == 2


def test_classify_bedrock_error_codes() -> None:
    throttled = classify_bedrock_error(FakeClientError("ThrottlingException"))
    validation = classify_bedrock_error(FakeClientError("ValidationException"))
    assert throttled is BedrockErrorClass.throttled
    assert validation is BedrockErrorClass.validation
    assert classify_bedrock_error(FakeClientError("ServiceUnavailableException")) is (
        BedrockErrorClass.unavailable
    )
    assert classify_bedrock_error(FakeClientError("ReadTimeoutError")) is BedrockErrorClass.timeout


def test_parse_bedrock_response_accepts_raw_review_object() -> None:
    payload = canned_output(ReviewType.category_suggestion)
    parsed = parse_bedrock_response({"body": json.dumps(payload)})
    assert isinstance(parsed, dict)
    assert parsed["review_type"] == "category_suggestion"


def test_parse_bedrock_response_reads_converse_tool_use() -> None:
    payload = canned_output(ReviewType.category_suggestion)
    parsed = parse_bedrock_response(
        {
            "output": {
                "message": {
                    "content": [{"toolUse": {"name": "submit_review_result", "input": payload}}]
                }
            }
        }
    )
    assert parsed == payload


def test_bedrock_does_not_retry_oversized_prompts() -> None:
    request = _request()
    reviewer = BedrockAIReviewer(
        FakeBedrock(canned_output(ReviewType.category_suggestion)),
        model_id="anthropic.claude-test",
        max_prompt_chars=8,
        sleep=lambda _: None,
    )
    with pytest.raises(ReviewerError, match="max payload"):
        reviewer.review(request)
