"""Validated reviewer output.

A provider may return JSON or a mapping. Anything that does not match this
schema is rejected; callers must not read a partial payload.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from retailops_api.review.types import (
    RecommendedAction,
    ReviewSchemaError,
    ReviewType,
    RiskLevel,
)

OUTPUT_SCHEMA_VERSION = "1"


class ReviewFindingModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    suggested_value: str | None = None
    field: str | None = None


class ReviewResult(BaseModel):
    """Structured result every reviewer implementation must produce."""

    model_config = ConfigDict(extra="forbid")

    review_type: ReviewType
    summary: str = Field(min_length=1)
    findings: list[ReviewFindingModel] = Field(default_factory=list)
    suggested_value: str | None = None
    reasoning_summary: str = Field(min_length=1)
    confidence: float
    risk: RiskLevel
    recommended_action: RecommendedAction
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    prompt_id: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    input_schema_version: str = Field(min_length=1)
    output_schema_version: str = Field(min_length=1)

    @field_validator("confidence")
    @classmethod
    def _confidence_unit_interval(cls, value: float) -> float:
        if value < 0 or value > 1:
            raise ValueError("confidence must be between 0 and 1 inclusive")
        return value

    @field_validator("output_schema_version")
    @classmethod
    def _known_output_schema(cls, value: str) -> str:
        if value != OUTPUT_SCHEMA_VERSION:
            raise ValueError(f"unsupported output_schema_version {value!r}")
        return value


def parse_review_result(raw: object) -> ReviewResult:
    """Validate provider output. Malformed payloads raise ``ReviewSchemaError``."""

    try:
        payload = _as_mapping(raw)
        return ReviewResult.model_validate(payload)
    except (ReviewSchemaError, ValidationError, TypeError, ValueError) as error:
        if isinstance(error, ReviewSchemaError):
            raise
        raise ReviewSchemaError(f"malformed reviewer output: {error}") from error


def _as_mapping(raw: object) -> dict[str, Any]:
    if isinstance(raw, ReviewResult):
        return raw.model_dump()
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as error:
            raise ReviewSchemaError(f"malformed reviewer output: {error}") from error
    if not isinstance(raw, dict):
        raise ReviewSchemaError("malformed reviewer output: expected an object")
    return raw
