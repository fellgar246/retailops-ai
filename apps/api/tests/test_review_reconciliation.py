from decimal import Decimal

from retailops_api.domain.models.reconciliation import ExceptionSeverity
from retailops_api.procurement.types import COST_MISMATCH, ProposedException
from retailops_api.review.mock import MockAIReviewer, MockBehavior, MockFixture, canned_output
from retailops_api.review.reconciliation import explain_exception, explain_exceptions
from retailops_api.review.types import RecommendedAction, ReviewEligibility, ReviewType, RiskLevel

IMPACT = Decimal("6.5000")


def _exception() -> ProposedException:
    return ProposedException(
        code=COST_MISMATCH,
        severity=ExceptionSeverity.error,
        message="invoice unit cost 8.1000 differs from PO 7.4500",
        expected_value="7.4500",
        actual_value="8.1000",
        financial_impact=IMPACT,
        purchase_order_id=1,
        supplier_invoice_id=5,
        product_id=100,
    )


def test_explanation_keeps_engine_amounts() -> None:
    reviewer = MockAIReviewer(
        {
            COST_MISMATCH: MockFixture(
                output=canned_output(
                    ReviewType.reconciliation_explanation,
                    summary="Price on the invoice is above the order.",
                    recommended_action=RecommendedAction.hold_payment.value,
                    risk=RiskLevel.high.value,
                    suggested_value="99.0000",
                )
            )
        }
    )

    explained = explain_exception(_exception(), reviewer)

    assert explained.amounts_from_engine
    assert explained.financial_impact == IMPACT
    assert explained.expected_value == "7.4500"
    assert explained.actual_value == "8.1000"
    assert explained.explanation == "Price on the invoice is above the order."
    assert explained.operational_risk is RiskLevel.high
    assert explained.suggested_action is RecommendedAction.hold_payment
    assert explained.routing.eligibility is ReviewEligibility.human_required


def test_malformed_explanation_does_not_invent_amounts() -> None:
    reviewer = MockAIReviewer(default_behavior=MockBehavior.malformed)
    item = _exception()

    explained = explain_exception(item, reviewer)

    assert explained.financial_impact == item.financial_impact
    assert explained.expected_value == item.expected_value
    assert explained.actual_value == item.actual_value
    assert explained.ai_result is None
    assert explained.explanation == item.message
    assert explained.routing.status.value == "failed_safe"


def test_batch_explains_each_exception() -> None:
    reviewer = MockAIReviewer()
    items = (_exception(),)

    explained = explain_exceptions(items, reviewer)

    assert len(explained) == 1
    assert explained[0].exception is items[0]
