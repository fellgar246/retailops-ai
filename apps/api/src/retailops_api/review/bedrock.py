"""Bedrock implementation of ``AIReviewer``.

Requests use the Bedrock Converse API with a JSON Schema tool so the
domain layer never sees Anthropic-specific request shapes. Responses are
validated with ``parse_review_result``. Retryable provider failures are
classified and retried; schema and authorization failures are not.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

from retailops_api.core.aws import DEFAULT_BEDROCK_MAX_TOKENS, DEFAULT_BEDROCK_TEMPERATURE
from retailops_api.core.limits import DEFAULT_MAX_PROMPT_CHARS
from retailops_api.core.retry import RetryPolicy
from retailops_api.review.output_schema import review_result_tool_config
from retailops_api.review.prompts import PromptSpec, get_prompt
from retailops_api.review.schemas import ReviewResult, parse_review_result
from retailops_api.review.types import ReviewerError, ReviewRequest, ReviewSchemaError
from retailops_api.review.usage import ProviderUsage, usage_from_converse

PROVIDER_ID = "bedrock"

SleepFn = Callable[[float], None]


class BedrockRuntimeClient(Protocol):
    """Subset of a boto3 Bedrock Runtime client used by this adapter."""

    def converse(self, **kwargs: Any) -> dict[str, Any]: ...


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
    "ReadTimeoutError": BedrockErrorClass.timeout,
    "ConnectTimeoutError": BedrockErrorClass.timeout,
    "ValidationException": BedrockErrorClass.validation,
    "ModelErrorException": BedrockErrorClass.validation,
    "AccessDeniedException": BedrockErrorClass.access_denied,
    "UnrecognizedClientException": BedrockErrorClass.access_denied,
    "ResourceNotFoundException": BedrockErrorClass.unavailable,
    "ServiceUnavailableException": BedrockErrorClass.unavailable,
    "InternalServerException": BedrockErrorClass.unavailable,
    "ModelNotReadyException": BedrockErrorClass.unavailable,
}


@dataclass(frozen=True)
class BedrockRequest:
    """Structured Converse arguments. Body is never Anthropic-native."""

    model_id: str
    messages: list[dict[str, Any]]
    inference_config: dict[str, Any]
    system: list[dict[str, str]]
    tool_config: dict[str, Any]


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
        max_tokens: int = DEFAULT_BEDROCK_MAX_TOKENS,
        temperature: float = DEFAULT_BEDROCK_TEMPERATURE,
        max_prompt_chars: int = DEFAULT_MAX_PROMPT_CHARS,
    ) -> None:
        if not model_id.strip():
            raise ReviewerError("Bedrock model id is required")
        self.client = client
        self.model_id = model_id.strip()
        self.region = region
        self.retry = retry or RetryPolicy()
        self._sleep = sleep or time.sleep
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.max_prompt_chars = max_prompt_chars
        self.last_usage: ProviderUsage | None = None

    @property
    def provider_id(self) -> str:
        return PROVIDER_ID

    def review(self, request: ReviewRequest) -> ReviewResult:
        spec = get_prompt(request.prompt_id, request.prompt_version)
        built = build_bedrock_request(
            request,
            model_id=self.model_id,
            template=spec.template,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            max_prompt_chars=self.max_prompt_chars,
        )
        raw = self._invoke(built)
        self.last_usage = usage_from_converse(raw, model_id=self.model_id, region=self.region)
        parsed = parse_bedrock_response(raw)
        stamped = _stamp_metadata(parsed, request=request, spec=spec, model_id=self.model_id)
        result = parse_review_result(stamped)
        return result.model_copy(
            update={
                "provider": self.provider_id,
                "model": self.model_id,
                "prompt_id": request.prompt_id,
                "prompt_version": request.prompt_version,
                "review_type": request.review_type,
                "input_schema_version": spec.input_schema_version,
                "output_schema_version": spec.output_schema_version,
            }
        )

    def _invoke(self, built: BedrockRequest) -> object:
        last_error: ReviewerError | None = None
        attempts = max(1, self.retry.max_attempts)
        for attempt in range(1, attempts + 1):
            try:
                return self.client.converse(
                    modelId=built.model_id,
                    messages=built.messages,
                    system=built.system,
                    inferenceConfig=built.inference_config,
                    toolConfig=built.tool_config,
                )
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
    max_tokens: int = DEFAULT_BEDROCK_MAX_TOKENS,
    temperature: float = DEFAULT_BEDROCK_TEMPERATURE,
    max_prompt_chars: int = DEFAULT_MAX_PROMPT_CHARS,
) -> BedrockRequest:
    """Build a Converse request with JSON Schema structured output."""

    schema_hint = (
        "Return the structured review result through the provided tool. "
        "Do not wrap the object in markdown. Do not recompute quantities, "
        "prices, VAT or other deterministic facts."
    )
    user_payload = {
        "instructions": template,
        "schema_hint": schema_hint,
        "request": request.to_dict(),
    }
    user_text = json.dumps(user_payload, sort_keys=True)
    if len(user_text) > max_prompt_chars:
        raise ReviewerError(f"Bedrock prompt exceeds max payload ({max_prompt_chars} characters)")
    return BedrockRequest(
        model_id=model_id,
        messages=[{"role": "user", "content": [{"text": user_text}]}],
        inference_config={
            "maxTokens": max_tokens,
            "temperature": temperature,
        },
        system=[{"text": schema_hint}],
        tool_config=review_result_tool_config(),
    )


def parse_bedrock_response(raw: object) -> object:
    """Extract a JSON object from a Converse or InvokeModel-style response."""

    payload = _as_mapping(raw)
    converse = _converse_payload(payload)
    if converse is not None:
        return converse
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
    if name in _CODE_CLASSES:
        return _CODE_CLASSES[name]
    if "Timeout" in name:
        return BedrockErrorClass.timeout
    return BedrockErrorClass.unknown


def _stamp_metadata(
    raw: object,
    *,
    request: ReviewRequest,
    spec: PromptSpec,
    model_id: str,
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ReviewSchemaError("Bedrock response is not an object")
    payload = dict(raw)
    payload.setdefault("provider", PROVIDER_ID)
    payload.setdefault("model", model_id)
    payload.setdefault("prompt_id", request.prompt_id)
    payload.setdefault("prompt_version", request.prompt_version)
    payload.setdefault("review_type", request.review_type.value)
    payload.setdefault("input_schema_version", spec.input_schema_version)
    payload.setdefault("output_schema_version", spec.output_schema_version)
    payload.setdefault("findings", [])
    return payload


def _converse_payload(payload: Mapping[str, Any]) -> object | None:
    output = payload.get("output")
    if not isinstance(output, dict):
        return None
    message = output.get("message")
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if not isinstance(content, list):
        return None
    for item in content:
        if not isinstance(item, dict):
            continue
        tool = item.get("toolUse")
        tool_input = tool.get("input") if isinstance(tool, dict) else None
        if isinstance(tool_input, dict):
            return tool_input
        text = item.get("text")
        if isinstance(text, str) and text.strip():
            return _loads_json_object(text)
    return None


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
