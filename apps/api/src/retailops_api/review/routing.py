"""Map confidence, risk and financial impact to review eligibility.

The default is human review. Auto-eligibility is a narrow exception: a valid
result, high confidence, low risk and no money at stake. High-risk cases
never auto-resolve. A failed or malformed provider call is ineligible and
must not be treated as a suggestion.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from retailops_api.review.schemas import ReviewResult
from retailops_api.review.types import (
    RecommendedAction,
    ReviewEligibility,
    ReviewerError,
    ReviewError,
    ReviewRouteStatus,
    ReviewSchemaError,
    RiskLevel,
)

DEFAULT_MIN_AUTO_CONFIDENCE = 0.85
DEFAULT_MAX_AUTO_ABS_IMPACT = Decimal("0.0000")


@dataclass(frozen=True)
class RoutingPolicy:
    min_auto_confidence: float = DEFAULT_MIN_AUTO_CONFIDENCE
    max_auto_abs_impact: Decimal = DEFAULT_MAX_AUTO_ABS_IMPACT
    auto_allowed_risk: frozenset[RiskLevel] = frozenset({RiskLevel.low})
    auto_allowed_actions: frozenset[RecommendedAction] = frozenset(
        {RecommendedAction.accept, RecommendedAction.no_action}
    )

    def to_dict(self) -> dict[str, object]:
        return {
            "min_auto_confidence": self.min_auto_confidence,
            "max_auto_abs_impact": str(self.max_auto_abs_impact),
            "auto_allowed_risk": sorted(item.value for item in self.auto_allowed_risk),
            "auto_allowed_actions": sorted(item.value for item in self.auto_allowed_actions),
            "rule": (
                "Human review unless the result is valid, confidence is at least "
                "the threshold, risk is low, absolute financial impact is at "
                "most the cap, and the recommended action is accept or no_action. "
                "High risk and provider failures never auto-resolve."
            ),
        }


DEFAULT_ROUTING_POLICY = RoutingPolicy()


@dataclass(frozen=True)
class RoutingDecision:
    eligibility: ReviewEligibility
    status: ReviewRouteStatus
    reasons: tuple[str, ...]
    financial_impact: Decimal

    def to_dict(self) -> dict[str, object]:
        return {
            "eligibility": self.eligibility.value,
            "status": self.status.value,
            "reasons": list(self.reasons),
            "financial_impact": str(self.financial_impact),
        }


def route(
    result: ReviewResult | None,
    *,
    financial_impact: Decimal = Decimal("0"),
    error: ReviewError | None = None,
    source_error_count: int = 0,
    policy: RoutingPolicy | None = None,
) -> RoutingDecision:
    """Decide whether a suggestion may skip the human queue."""

    settings = policy or DEFAULT_ROUTING_POLICY
    impact = abs(financial_impact)
    reasons: list[str] = []

    if error is not None:
        reasons.extend(_failure_reasons(error))
        return RoutingDecision(
            eligibility=ReviewEligibility.ineligible,
            status=ReviewRouteStatus.failed_safe,
            reasons=tuple(reasons),
            financial_impact=financial_impact,
        )
    if result is None:
        return RoutingDecision(
            eligibility=ReviewEligibility.human_required,
            status=ReviewRouteStatus.pending_human,
            reasons=("no_reviewer_output",),
            financial_impact=financial_impact,
        )

    if result.risk is RiskLevel.high:
        reasons.append("high_risk_requires_human")
    elif result.risk not in settings.auto_allowed_risk:
        reasons.append("risk_not_auto_eligible")
    if result.confidence < settings.min_auto_confidence:
        reasons.append("confidence_below_threshold")
    if impact > settings.max_auto_abs_impact:
        reasons.append("financial_impact_requires_human")
    if result.recommended_action is RecommendedAction.human_review:
        reasons.append("reviewer_requested_human")
    elif result.recommended_action not in settings.auto_allowed_actions:
        reasons.append("action_requires_human")
    if source_error_count > 0:
        reasons.append("deterministic_errors_require_human")

    if reasons:
        return RoutingDecision(
            eligibility=ReviewEligibility.human_required,
            status=ReviewRouteStatus.pending_human,
            reasons=tuple(reasons),
            financial_impact=financial_impact,
        )

    return RoutingDecision(
        eligibility=ReviewEligibility.auto_eligible,
        status=ReviewRouteStatus.suggestion_ready,
        reasons=("meets_auto_eligibility",),
        financial_impact=financial_impact,
    )


def route_from_attributes(
    *,
    confidence: float,
    risk: RiskLevel,
    recommended_action: RecommendedAction,
    financial_impact: Decimal = Decimal("0"),
    policy: RoutingPolicy | None = None,
) -> RoutingDecision:
    """Score a routing case that already has structured attributes."""

    from retailops_api.review.prompts import CATEGORY_SUGGESTION_V1
    from retailops_api.review.schemas import OUTPUT_SCHEMA_VERSION
    from retailops_api.review.types import ReviewType

    result = ReviewResult(
        review_type=ReviewType.category_suggestion,
        summary="Routing attributes only.",
        findings=[],
        suggested_value=None,
        reasoning_summary="Synthetic result for routing evaluation.",
        confidence=confidence,
        risk=risk,
        recommended_action=recommended_action,
        provider="policy",
        model="routing",
        prompt_id=CATEGORY_SUGGESTION_V1.prompt_id,
        prompt_version=CATEGORY_SUGGESTION_V1.version,
        input_schema_version=CATEGORY_SUGGESTION_V1.input_schema_version,
        output_schema_version=OUTPUT_SCHEMA_VERSION,
    )
    return route(result, financial_impact=financial_impact, policy=policy)


def _failure_reasons(error: ReviewError | None) -> list[str]:
    if isinstance(error, ReviewerError):
        return ["provider_failure"]
    if isinstance(error, ReviewSchemaError):
        return ["malformed_output"]
    if error is not None:
        return ["review_failed"]
    return ["missing_result"]
