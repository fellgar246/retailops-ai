from decimal import Decimal
from typing import Any

from retailops_api.review.mock import canned_output
from retailops_api.review.routing import route, route_from_attributes
from retailops_api.review.schemas import ReviewResult, parse_review_result
from retailops_api.review.types import (
    RecommendedAction,
    ReviewEligibility,
    ReviewerError,
    ReviewRouteStatus,
    ReviewSchemaError,
    ReviewType,
    RiskLevel,
)


def _result(**overrides: Any) -> ReviewResult:
    payload = canned_output(ReviewType.category_suggestion, **overrides)
    return parse_review_result(payload)


def test_high_confidence_low_risk_zero_impact_may_auto_apply() -> None:
    decision = route(
        _result(
            confidence=0.92,
            risk=RiskLevel.low.value,
            recommended_action=RecommendedAction.accept.value,
        )
    )

    assert decision.eligibility is ReviewEligibility.auto_eligible
    assert decision.status is ReviewRouteStatus.suggestion_ready


def test_low_confidence_requires_a_human() -> None:
    decision = route(_result(confidence=0.4, recommended_action=RecommendedAction.accept.value))

    assert decision.eligibility is ReviewEligibility.human_required
    assert "confidence_below_threshold" in decision.reasons


def test_high_risk_never_auto_resolves() -> None:
    decision = route(
        _result(
            confidence=0.99,
            risk=RiskLevel.high.value,
            recommended_action=RecommendedAction.accept.value,
        )
    )

    assert decision.eligibility is ReviewEligibility.human_required
    assert "high_risk_requires_human" in decision.reasons


def test_any_financial_impact_requires_a_human() -> None:
    decision = route(
        _result(confidence=0.95, recommended_action=RecommendedAction.accept.value),
        financial_impact=Decimal("0.0100"),
    )

    assert decision.eligibility is ReviewEligibility.human_required
    assert "financial_impact_requires_human" in decision.reasons


def test_deterministic_errors_cannot_be_bypassed() -> None:
    decision = route(
        _result(confidence=0.95, recommended_action=RecommendedAction.accept.value),
        source_error_count=2,
    )

    assert decision.eligibility is ReviewEligibility.human_required
    assert "deterministic_errors_require_human" in decision.reasons


def test_malformed_output_fails_safe() -> None:
    decision = route(None, error=ReviewSchemaError("malformed reviewer output"))

    assert decision.eligibility is ReviewEligibility.ineligible
    assert decision.status is ReviewRouteStatus.failed_safe
    assert "malformed_output" in decision.reasons


def test_provider_failure_fails_safe() -> None:
    decision = route(None, error=ReviewerError("down"))

    assert decision.eligibility is ReviewEligibility.ineligible
    assert decision.status is ReviewRouteStatus.failed_safe


def test_missing_reviewer_is_human_review_not_a_failure() -> None:
    decision = route(None)

    assert decision.eligibility is ReviewEligibility.human_required
    assert decision.status is ReviewRouteStatus.pending_human
    assert decision.reasons == ("no_reviewer_output",)


def test_routing_attributes_match_the_policy() -> None:
    auto = route_from_attributes(
        confidence=0.9,
        risk=RiskLevel.low,
        recommended_action=RecommendedAction.accept,
        financial_impact=Decimal("0"),
    )
    human = route_from_attributes(
        confidence=0.9,
        risk=RiskLevel.low,
        recommended_action=RecommendedAction.escalate,
        financial_impact=Decimal("0"),
    )

    assert auto.eligibility is ReviewEligibility.auto_eligible
    assert human.eligibility is ReviewEligibility.human_required
