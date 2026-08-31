"""Bedrock implementation of ``AIReviewer``.

The client is injected. Requests are built as structured JSON, responses are
parsed and then validated with ``parse_review_result``. Retryable provider
failures are classified and retried; schema failures are not.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

from retailops_api.review.prompts import get_prompt
from retailops_api.review.schemas import ReviewResult, parse_review_result
from retailops_api.review.types import ReviewerError, ReviewRequest, ReviewSchemaError

PROVIDER_ID = "bedrock"

SleepFn = Callable[[float], None]


class BedrockRuntimeClient(Protocol):
    """Subset of a boto3 Bedrock Runtime client used by this adapter."""

    def invoke_model(self, **kwargs: Any) -> dict[str, Any]: ...


class BedrockErrorClass(StrEnum):
    throttled = "throttled"
    timeout = "timeout"
    validation = "validation"
    access_denied = "access_denied"
    unavailable = "unavailable"
    unknown = "unknown"


_RETRYABLE = frozenset(
    {BedrockErrorClass.throttled, BedrockErrorClass.unavailable, BedrockErrorClass.timeout}
)

_CODE_CLASSES: dict[str, BedrockErrorClass] = {
    "ThrottlingException": BedrockErrorClass.throttled,
    "TooManyRequestsException": BedrockErrorClass.throttled,
    "ModelTimeoutException": BedrockErrorClass.timeout,
    "Timeout": BedrockErrorClass.timeout,
    "ValidationException": BedrockErrorClass.validation,
    "ModelErrorException": BedrockErrorClass.validation,
    "AccessDeniedException": BedrockErrorClass.access_denied,
    "UnrecognizedClientException": BedrockErrorClass.access_denied,
    "ServiceUnavailableException": BedrockErrorClass.unavailable,
    "InternalServerException": BedrockErrorClass.unavailable,
    "ModelNotReadyException": BedrockErrorClass.unavailable,
}


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay_seconds: float = 0.2

    def delay_for(self, attempt: int) -> float:
        if self.base_delay_seconds <= 0:
            return 0.0
        return self.base_delay_seconds * attempt


@dataclass(frozen=True)
class BedrockRequest:
    """Structured InvokeModel arguments (body is still a mapping, not bytes)."""

    model_id: str
    content_type: str
    accept: str
    body: dict[str, Any]


class BedrockAIReviewer:
    """Hosted reviewer behind the same ``review`` method as the mock."""

    def __init__(
        self,
        client: BedrockRuntimeClient,
        *,
        model_id: str,
        region: str = "us-east-1",
        retry: RetryPolicy | None = None,
        sleep: SleepFn | None = None,
    ) -> None:
        if not model_id.strip():
            raise ReviewerError("Bedrock model id is required")
        self.client = client
        self.model_id = model_id.strip()
        self.region = region
        self.retry = retry or RetryPolicy()
        self._sleep = sleep or time.sleep

    @property
    def provider_id(self) -> str:
        return PROVIDER_ID

    def review(self, request: ReviewRequest) -> ReviewResult:
        spec = get_prompt(request.prompt_id, request.prompt_version)
        built = build_bedrock_request(request, model_id=self.model_id, template=spec.template)
        raw = self._invoke(built)
        parsed = parse_bedrock_response(raw)
        result = parse_review_result(parsed)
        return result.model_copy(
            update={
                "provider": self.provider_id,
                "model": self.model_id,
                "prompt_id": request.prompt_id,
                "prompt_version": request.prompt_version,
                "review_type": request.review_type,
            }
        )

    def _invoke(self, built: BedrockRequest) -> object:
        last_error: ReviewerError | None = None
        attempts = max(1, self.retry.max_attempts)
        for attempt in range(1, attempts + 1):
            try:
                response = self.client.invoke_model(
                    modelId=built.model_id,
                    contentType=built.content_type,
                    accept=built.accept,
                    body=json.dumps(built.body).encode("utf-8"),
                )
                return response
            except ReviewerError:
                raise
            except Exception as error:
                classified = classify_bedrock_error(error)
                last_error = ReviewerError(f"Bedrock invoke failed ({classified.value}): {error}")
                if classified not in _RETRYABLE or attempt >= attempts:
                    raise last_error from error
                self._sleep(self.retry.delay_for(attempt))
        raise last_error or ReviewerError("Bedrock invoke failed")


def build_bedrock_request(
    request: ReviewRequest,
    *,
    model_id: str,
    template: str,
) -> BedrockRequest:
    """Build a structured InvokeModel body for a Claude-compatible model."""

    schema_hint = (
        "Return a single JSON object that matches the review result schema. "
        "Do not wrap the object in markdown."
    )
    user_payload = {
        "instructions": template,
        "schema_hint": schema_hint,
        "request": request.to_dict(),
    }
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 2048,
        "temperature": 0,
        "system": schema_hint,
        "messages": [
            {
                "role": "user",
                "content": json.dumps(user_payload, sort_keys=True),
            }
        ],
    }
    return BedrockRequest(
        model_id=model_id,
        content_type="application/json",
        accept="application/json",
        body=body,
    )


def parse_bedrock_response(raw: object) -> object:
    """Extract a JSON object from an InvokeModel-style response."""

    payload = _as_mapping(raw)
    body = payload.get("body", payload)
    decoded = _decode_body(body)
    if isinstance(decoded, dict):
        text = _content_text(decoded)
        if text is not None:
            return _loads_json_object(text)
        if _looks_like_review(decoded):
            return decoded
        completion = decoded.get("completion")
        if isinstance(completion, str):
            return _loads_json_object(completion)
    if isinstance(decoded, str):
        return _loads_json_object(decoded)
    raise ReviewSchemaError("Bedrock response did not contain a JSON object")


def classify_bedrock_error(error: BaseException) -> BedrockErrorClass:
    response = getattr(error, "response", None)
    if isinstance(response, dict):
        payload = response.get("Error")
        if isinstance(payload, dict) and payload.get("Code") is not None:
            return _CODE_CLASSES.get(str(payload["Code"]), BedrockErrorClass.unknown)
    code = getattr(error, "code", None)
    if code is not None:
        return _CODE_CLASSES.get(str(code), BedrockErrorClass.unknown)
    name = type(error).__name__
    return _CODE_CLASSES.get(name, BedrockErrorClass.unknown)


def _as_mapping(raw: object) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    raise ReviewSchemaError("Bedrock response is not an object")


def _decode_body(body: object) -> object:
    if hasattr(body, "read") and callable(body.read):
        body = body.read()
    if isinstance(body, (bytes, bytearray)):
        body = body.decode("utf-8")
    if isinstance(body, str):
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return body
    return body


def _content_text(payload: Mapping[str, Any] | dict[str, Any]) -> str | None:
    content = payload.get("content")
    if isinstance(content, str) and content.strip():
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("text"):
                parts.append(str(item["text"]))
        if parts:
            return "\n".join(parts)
    return None


def _looks_like_review(payload: dict[str, Any]) -> bool:
    return "review_type" in payload and "confidence" in payload and "summary" in payload


def _loads_json_object(text: str) -> object:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.removeprefix("```json").removeprefix("```").strip()
        if stripped.endswith("```"):
            stripped = stripped[:-3].strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError as error:
        raise ReviewSchemaError(f"Bedrock response is not valid JSON: {error}") from error
