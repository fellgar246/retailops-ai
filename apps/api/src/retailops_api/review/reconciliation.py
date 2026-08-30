"""Explain reconciliation exceptions without touching the match arithmetic.

Expected and actual values and the signed financial impact come from the
reconciliation engine. The reviewer may only write an explanation, an
operational risk and a suggested action.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from retailops_api.procurement.types import ProposedException, ReconciliationResult
from retailops_api.review.contract import AIReviewer, SafeReview, build_request, review_safely
from retailops_api.review.routing import RoutingDecision, route
from retailops_api.review.schemas import ReviewResult
from retailops_api.review.types import (
    RecommendedAction,
    ReconciliationExplanationInput,
    ReviewType,
    RiskLevel,
)


@dataclass(frozen=True)
class ExceptionExplanation:
    exception: ProposedException
    explanation: str
    operational_risk: RiskLevel
    suggested_action: RecommendedAction
    financial_impact: Decimal
    expected_value: str
    actual_value: str
    ai_result: ReviewResult | None
    routing: RoutingDecision
    attempt: SafeReview | None

    @property
    def amounts_from_engine(self) -> bool:
        return (
            self.financial_impact == self.exception.financial_impact
            and self.expected_value == self.exception.expected_value
            and self.actual_value == self.exception.actual_value
        )


def explain_exception(
    item: ProposedException,
    reviewer: AIReviewer,
    *,
    purchase_order_number: str | None = None,
    invoice_number: str | None = None,
    product_sku: str | None = None,
    case_id: str | None = None,
) -> ExceptionExplanation:
    payload = ReconciliationExplanationInput.from_exception(
        item,
        purchase_order_number=purchase_order_number,
        invoice_number=invoice_number,
        product_sku=product_sku,
    )
    request = build_request(
        ReviewType.reconciliation_explanation,
        payload,
        case_id=case_id or item.code,
    )
    attempt = review_safely(reviewer, request)
    result = attempt.result
    routing = route(
        result,
        financial_impact=item.financial_impact,
        error=attempt.error,
    )
    return ExceptionExplanation(
        exception=item,
        explanation=_explanation(item, result),
        operational_risk=_risk(item, result),
        suggested_action=_action(result),
        financial_impact=item.financial_impact,
        expected_value=item.expected_value,
        actual_value=item.actual_value,
        ai_result=result,
        routing=routing,
        attempt=attempt,
    )


def explain_reconciliation_result(
    result: ReconciliationResult,
    reviewer: AIReviewer,
    *,
    purchase_order_number: str | None = None,
    invoice_number: str | None = None,
) -> tuple[ExceptionExplanation, ...]:
    return tuple(
        explain_exception(
            item,
            reviewer,
            purchase_order_number=purchase_order_number,
            invoice_number=invoice_number,
            case_id=f"{result.scope_key}:{item.code}:{index}",
        )
        for index, item in enumerate(result.exceptions)
    )


def explain_exceptions(
    exceptions: Sequence[ProposedException],
    reviewer: AIReviewer,
) -> tuple[ExceptionExplanation, ...]:
    return tuple(explain_exception(item, reviewer, case_id=item.code) for item in exceptions)


def _explanation(item: ProposedException, result: ReviewResult | None) -> str:
    if result is not None:
        return result.summary
    return item.message


def _risk(item: ProposedException, result: ReviewResult | None) -> RiskLevel:
    if result is not None:
        return result.risk
    if item.severity.value == "error":
        return RiskLevel.high
    if item.severity.value == "warning":
        return RiskLevel.medium
    return RiskLevel.low


def _action(result: ReviewResult | None) -> RecommendedAction:
    if result is None:
        return RecommendedAction.human_review
    return result.recommended_action
