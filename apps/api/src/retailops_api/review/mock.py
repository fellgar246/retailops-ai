"""Deterministic reviewer test double.

The mock plays back fixtures. It does not infer categories, write summaries
from findings, or otherwise emulate a model.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from retailops_api.review.prompts import prompt_for
from retailops_api.review.schemas import OUTPUT_SCHEMA_VERSION, ReviewResult, parse_review_result
from retailops_api.review.types import (
    MockBehavior,
    RecommendedAction,
    ReviewerError,
    ReviewRequest,
    ReviewType,
    RiskLevel,
)

__all__ = [
    "MockAIReviewer",
    "MockBehavior",
    "MockFixture",
    "canned_output",
]

PROVIDER_ID = "mock"
MODEL_ID = "fixture"


@dataclass(frozen=True)
class MockFixture:
    behavior: MockBehavior = MockBehavior.normal
    output: dict[str, Any] | None = None


def _base_output(review_type: ReviewType) -> dict[str, Any]:
    spec = prompt_for(review_type)
    return {
        "review_type": review_type.value,
        "summary": "Fixture summary.",
        "findings": [],
        "suggested_value": "BEV-SOFT",
        "reasoning_summary": "Canned fixture output.",
        "confidence": 0.91,
        "risk": RiskLevel.low.value,
        "recommended_action": RecommendedAction.human_review.value,
        "provider": PROVIDER_ID,
        "model": MODEL_ID,
        "prompt_id": spec.prompt_id,
        "prompt_version": spec.version,
        "input_schema_version": spec.input_schema_version,
        "output_schema_version": OUTPUT_SCHEMA_VERSION,
    }


def canned_output(
    review_type: ReviewType,
    *,
    behavior: MockBehavior = MockBehavior.normal,
    **overrides: Any,
) -> dict[str, Any]:
    """A valid (or intentionally broken) payload for tests and fixtures."""

    if behavior is MockBehavior.malformed:
        payload = {"summary": 1, "confidence": "not-a-number"}
        payload.update(overrides)
        return payload
    payload = _base_output(review_type)
    if behavior is MockBehavior.low_confidence:
        payload["confidence"] = 0.22
        payload["risk"] = RiskLevel.medium.value
        payload["recommended_action"] = RecommendedAction.human_review.value
        payload["reasoning_summary"] = "Low-confidence fixture output."
    payload.update(overrides)
    return payload


class MockAIReviewer:
    """Lookup-only reviewer. Missing fixtures use ``default_behavior``."""

    def __init__(
        self,
        fixtures: Mapping[str, MockFixture] | None = None,
        *,
        default_behavior: MockBehavior = MockBehavior.normal,
    ) -> None:
        self._fixtures = dict(fixtures or {})
        self._default = default_behavior

    @property
    def provider_id(self) -> str:
        return PROVIDER_ID

    def review(self, request: ReviewRequest) -> ReviewResult:
        fixture = self._lookup(request)
        if fixture.behavior is MockBehavior.provider_failure:
            raise ReviewerError("mock provider failure")
        raw = (
            fixture.output
            if fixture.output is not None
            else canned_output(request.review_type, behavior=fixture.behavior)
        )
        raw = _align_metadata(raw, request)
        return parse_review_result(raw)

    def _lookup(self, request: ReviewRequest) -> MockFixture:
        if request.case_id and request.case_id in self._fixtures:
            return self._fixtures[request.case_id]
        return MockFixture(behavior=self._default)


def _align_metadata(raw: dict[str, Any], request: ReviewRequest) -> dict[str, Any]:
    if "summary" in raw and not isinstance(raw.get("summary"), str):
        return raw
    aligned = dict(raw)
    aligned.setdefault("review_type", request.review_type.value)
    aligned.setdefault("prompt_id", request.prompt_id)
    aligned.setdefault("prompt_version", request.prompt_version)
    aligned.setdefault("provider", PROVIDER_ID)
    aligned.setdefault("model", MODEL_ID)
    return aligned
