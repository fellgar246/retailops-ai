"""AI-assisted review contracts, human-oversight cases and an evaluation harness.

Callers talk to ``AIReviewer``. The local implementation is a fixture double.
A hosted model adapter implements the same method. Deterministic findings and
reconciliation amounts stay the source of truth. Human decisions, the audit
log and feedback rows live alongside those contracts.
"""

from retailops_api.review.bedrock import BedrockAIReviewer
from retailops_api.review.cases import (
    ALLOWED_TRANSITIONS,
    ReviewConflictError,
    ReviewFilters,
    ReviewNotFoundError,
    ReviewPriority,
    ReviewStatus,
    ReviewSubjectType,
    ReviewValidationError,
    can_transition,
)
from retailops_api.review.cloud_workflow import LocalCallbackWorkflow
from retailops_api.review.contract import AIReviewer, SafeReview, build_request, review_safely
from retailops_api.review.metrics import ReviewMetrics, collect_metrics
from retailops_api.review.mock import MockAIReviewer, MockFixture
from retailops_api.review.persist import create_review_case
from retailops_api.review.policy import ALLOWED_USES, DEFAULT_USAGE_POLICY, FORBIDDEN_USES
from retailops_api.review.queue import list_cases
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
from retailops_api.review.workflow import (
    approve_review,
    assign_review,
    cancel_review,
    correct_review,
    reject_review,
    start_review,
)

__all__ = [
    "ALLOWED_TRANSITIONS",
    "ALLOWED_USES",
    "DEFAULT_ROUTING_POLICY",
    "DEFAULT_USAGE_POLICY",
    "FORBIDDEN_USES",
    "AIReviewer",
    "BedrockAIReviewer",
    "ExceptionExplanation",
    "LocalCallbackWorkflow",
    "MockAIReviewer",
    "MockFixture",
    "RecommendedAction",
    "ReviewConflictError",
    "ReviewEligibility",
    "ReviewFilters",
    "ReviewMetrics",
    "ReviewNotFoundError",
    "ReviewPriority",
    "ReviewRequest",
    "ReviewResult",
    "ReviewStatus",
    "ReviewSubjectType",
    "ReviewType",
    "ReviewValidationError",
    "RiskLevel",
    "RoutingDecision",
    "SafeReview",
    "SupplierSemanticReview",
    "approve_review",
    "assign_review",
    "build_request",
    "can_transition",
    "cancel_review",
    "collect_metrics",
    "correct_review",
    "create_review_case",
    "explain_exceptions",
    "list_cases",
    "parse_review_result",
    "reject_review",
    "review_safely",
    "review_supplier_sheet",
    "route",
    "start_review",
]
