from decimal import Decimal

from retailops_api.documents.catalog_rules import CATEGORY_MISMATCH
from retailops_api.documents.types import Finding, SupplierSheetRow
from retailops_api.domain.models.document import FindingSeverity
from retailops_api.review.mock import MockAIReviewer, MockBehavior, MockFixture, canned_output
from retailops_api.review.supplier import review_supplier_sheet
from retailops_api.review.types import (
    RecommendedAction,
    ReviewEligibility,
    ReviewType,
    SupplierSheetContext,
)


def _row(**overrides: object) -> SupplierSheetRow:
    values: dict[str, object] = {
        "row_number": 2,
        "supplier_sku": "NW-1",
        "ean": "7501999000011",
        "description": "Cola",
        "category": "refrescos",
        "cost": Decimal("1.0000"),
        "vat": Decimal("16"),
        "case_pack": 12,
        "minimum_order_quantity": 1,
        "lead_time_days": 3,
    }
    values.update(overrides)
    return SupplierSheetRow(**values)  # type: ignore[arg-type]


def _finding(
    code: str = CATEGORY_MISMATCH,
    *,
    severity: FindingSeverity = FindingSeverity.warning,
    field: str = "category",
    proposed: str | None = "BEV-SOFT",
) -> Finding:
    return Finding(
        code=code,
        severity=severity,
        message=f"{code} on {field}",
        field=field,
        row_number=2,
        proposed_value=proposed,
    )


def test_deterministic_findings_are_unchanged() -> None:
    findings = (_finding(),)
    context = SupplierSheetContext(
        supplier_code="SUP-BEVCO",
        filename="offer.csv",
        rows=(_row(),),
        findings=findings,
        catalog_codes=("BEV-SOFT",),
        catalog_names=("Soft drinks",),
    )
    reviewer = MockAIReviewer()

    outcome = review_supplier_sheet(context, reviewer)

    assert outcome.findings is findings
    assert outcome.source_of_truth == findings
    assert outcome.findings[0].code == CATEGORY_MISMATCH
    assert outcome.findings[0].proposed_value == "BEV-SOFT"


def test_reviewer_adds_category_suggestion_and_summary() -> None:
    context = SupplierSheetContext(
        supplier_code="SUP-BEVCO",
        filename="offer.csv",
        rows=(_row(),),
        findings=(_finding(),),
        catalog_codes=("BEV-SOFT",),
        catalog_names=("Soft drinks",),
        document_id=9,
    )
    reviewer = MockAIReviewer(
        {
            "SUP-BEVCO:9:category:refrescos": MockFixture(
                output=canned_output(
                    ReviewType.category_suggestion,
                    suggested_value="BEV-SOFT",
                )
            ),
            "SUP-BEVCO:9:summary:offer.csv": MockFixture(
                output=canned_output(
                    ReviewType.supplier_summary,
                    summary="Category mismatch needs a correction.",
                    recommended_action=RecommendedAction.request_correction.value,
                    risk="medium",
                )
            ),
        }
    )

    outcome = review_supplier_sheet(context, reviewer)

    assert outcome.category_suggestions[0].suggested_value == "BEV-SOFT"
    assert outcome.summary == "Category mismatch needs a correction."
    assert outcome.recommended_action is RecommendedAction.request_correction
    assert outcome.ai_result is not None


def test_without_a_reviewer_findings_still_drive_the_outcome() -> None:
    findings = (
        _finding(
            "required_field",
            severity=FindingSeverity.error,
            field="description",
            proposed=None,
        ),
    )
    context = SupplierSheetContext(
        supplier_code="SUP-BEVCO",
        filename="offer.csv",
        rows=(_row(description=None),),
        findings=findings,
    )

    outcome = review_supplier_sheet(context, reviewer=None)

    assert outcome.findings == findings
    assert outcome.category_suggestions == ()
    assert outcome.ai_result is None
    assert outcome.recommended_action is RecommendedAction.request_correction
    assert outcome.routing.eligibility is ReviewEligibility.human_required
    assert "error" in outcome.summary


def test_provider_failure_does_not_replace_findings() -> None:
    findings = (_finding(),)
    context = SupplierSheetContext(
        supplier_code="SUP-BEVCO",
        filename="offer.csv",
        rows=(_row(),),
        findings=findings,
        catalog_codes=("BEV-SOFT",),
    )
    reviewer = MockAIReviewer(default_behavior=MockBehavior.provider_failure)

    outcome = review_supplier_sheet(context, reviewer)

    assert outcome.findings is findings
    assert outcome.ai_result is None
    assert outcome.routing.eligibility is ReviewEligibility.ineligible
    assert outcome.routing.status.value == "failed_safe"
