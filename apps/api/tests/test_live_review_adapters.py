from decimal import Decimal

from retailops_api.documents.catalog_rules import CATEGORY_MISMATCH
from retailops_api.documents.types import Finding, SupplierSheetRow
from retailops_api.domain.models.document import FindingSeverity
from retailops_api.domain.models.reconciliation import ExceptionSeverity
from retailops_api.procurement.types import ProposedException
from retailops_api.review.bedrock import BedrockAIReviewer
from retailops_api.review.mock import canned_output
from retailops_api.review.reconciliation import explain_exception
from retailops_api.review.supplier import review_supplier_sheet
from retailops_api.review.types import ReviewType, SupplierSheetContext
from tests.aws_fakes import FakeBedrock


def test_supplier_semantic_review_accepts_bedrock_adapter() -> None:
    reviewer = BedrockAIReviewer(
        FakeBedrock(canned_output(ReviewType.supplier_summary, summary="Prioritize the category.")),
        model_id="anthropic.claude-test",
        sleep=lambda _: None,
    )
    result = review_supplier_sheet(
        SupplierSheetContext(
            supplier_code="SUP-BEVCO",
            filename="offer.pdf",
            rows=(
                SupplierSheetRow(
                    row_number=2,
                    supplier_sku="NW-1",
                    category="refrescos",
                    description="Cola",
                ),
            ),
            findings=(
                Finding(
                    code=CATEGORY_MISMATCH,
                    severity=FindingSeverity.warning,
                    message="category does not match",
                    field="category",
                    row_number=2,
                ),
            ),
            catalog_codes=("BEV-SOFT",),
        ),
        reviewer,
    )
    assert result.ai_result is not None
    assert result.ai_result.provider == "bedrock"
    assert result.findings[0].code == CATEGORY_MISMATCH
    assert result.source_of_truth == result.findings


def test_reconciliation_explanation_keeps_engine_facts_with_bedrock() -> None:
    reviewer = BedrockAIReviewer(
        FakeBedrock(
            canned_output(
                ReviewType.reconciliation_explanation,
                summary="Invoice billed two extra units.",
                suggested_value="99",
            )
        ),
        model_id="anthropic.claude-test",
        sleep=lambda _: None,
    )
    explained = explain_exception(
        ProposedException(
            code="qty_invoice_over",
            severity=ExceptionSeverity.warning,
            message="invoiced 12 received 10",
            expected_value="10",
            actual_value="12",
            financial_impact=Decimal("20.00"),
        ),
        reviewer,
    )
    assert explained.amounts_from_engine
    assert explained.expected_value == "10"
    assert explained.actual_value == "12"
    assert explained.financial_impact == Decimal("20.00")
    assert explained.ai_result is not None
    assert explained.ai_result.provider == "bedrock"
