"""AI-assisted review contracts, a mock reviewer and an evaluation harness.

Callers talk to ``AIReviewer``. The local implementation is a fixture double.
A hosted model adapter implements the same method. Deterministic findings and
reconciliation amounts stay the source of truth.
"""

from retailops_api.review.contract import AIReviewer, SafeReview, build_request, review_safely
from retailops_api.review.mock import MockAIReviewer, MockFixture
from retailops_api.review.policy import ALLOWED_USES, DEFAULT_USAGE_POLICY, FORBIDDEN_USES
from retailops_api.review.reconciliation import ExceptionExplanation, explain_exceptions
from retailops_api.review.routing import DEFAULT_ROUTING_POLICY, RoutingDecision, route
from retailops_api.review.schemas import ReviewResult, parse_review_result
from retailops_api.review.supplier import SupplierSemanticReview, review_supplier_sheet
from retailops_api.review.types import (
    RecommendedAction,
    ReviewEligibility,
    ReviewRequest,
    ReviewType,
    RiskLevel,
)

__all__ = [
    "ALLOWED_USES",
    "DEFAULT_ROUTING_POLICY",
    "DEFAULT_USAGE_POLICY",
    "FORBIDDEN_USES",
    "AIReviewer",
    "ExceptionExplanation",
    "MockAIReviewer",
    "MockFixture",
    "RecommendedAction",
    "ReviewEligibility",
    "ReviewRequest",
    "ReviewResult",
    "ReviewType",
    "RiskLevel",
    "RoutingDecision",
    "SafeReview",
    "SupplierSemanticReview",
    "build_request",
    "explain_exceptions",
    "parse_review_result",
    "review_safely",
    "review_supplier_sheet",
    "route",
]
