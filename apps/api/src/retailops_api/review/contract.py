"""Provider-neutral reviewer interface.

Inputs are domain DTOs. Outputs must pass ``parse_review_result``. A hosted
model adapter implements the same ``review`` method; callers do not change.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from retailops_api.review.prompts import get_prompt, prompt_for
from retailops_api.review.schemas import ReviewResult, parse_review_result
from retailops_api.review.types import (
    ReviewerError,
    ReviewError,
    ReviewPayload,
    ReviewRequest,
    ReviewSchemaError,
    ReviewType,
)


class AIReviewer(Protocol):
    """Semantic review. Implementations must not assume a cloud vendor."""

    @property
    def provider_id(self) -> str: ...

    def review(self, request: ReviewRequest) -> ReviewResult:
        """Return a validated structured result or raise a review error."""
        ...


@dataclass(frozen=True)
class SafeReview:
    """Outcome of a guarded call: a valid result, or a typed failure."""

    result: ReviewResult | None
    error: ReviewError | None

    @property
    def ok(self) -> bool:
        return self.result is not None and self.error is None

    @property
    def schema_valid(self) -> bool:
        return self.result is not None

    @property
    def provider_failed(self) -> bool:
        return isinstance(self.error, ReviewerError)

    @property
    def schema_failed(self) -> bool:
        return isinstance(self.error, ReviewSchemaError)


def build_request(
    review_type: ReviewType,
    payload: ReviewPayload,
    *,
    case_id: str | None = None,
    prompt_id: str | None = None,
    prompt_version: str | None = None,
) -> ReviewRequest:
    spec = (
        get_prompt(prompt_id, prompt_version) if prompt_id is not None else prompt_for(review_type)
    )
    if prompt_id is None and prompt_version is not None:
        spec = get_prompt(spec.prompt_id, prompt_version)
    return ReviewRequest(
        review_type=review_type,
        payload=payload,
        prompt_id=spec.prompt_id,
        prompt_version=spec.version,
        case_id=case_id,
    )


def review_safely(reviewer: AIReviewer, request: ReviewRequest) -> SafeReview:
    """Call a reviewer and convert failures into a safe, unused result."""

    try:
        result = reviewer.review(request)
        parsed = parse_review_result(result)
        return SafeReview(result=parsed, error=None)
    except ReviewerError as error:
        return SafeReview(result=None, error=error)
    except ReviewSchemaError as error:
        return SafeReview(result=None, error=error)
    except ReviewError as error:
        return SafeReview(result=None, error=error)
