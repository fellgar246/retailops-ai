"""Shared enums, errors and domain DTOs for AI-assisted review.

Persistence of human decisions is a separate workflow. These shapes are what
a reviewer receives and what routing / evaluation inspect.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Any

from retailops_api.documents.types import Finding, SupplierSheetRow
from retailops_api.procurement.types import ProposedException


class ReviewType(StrEnum):
    category_suggestion = "category_suggestion"
    supplier_summary = "supplier_summary"
    reconciliation_explanation = "reconciliation_explanation"


class RiskLevel(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"


class RecommendedAction(StrEnum):
    accept = "accept"
    request_correction = "request_correction"
    escalate = "escalate"
    hold_payment = "hold_payment"
    no_action = "no_action"
    human_review = "human_review"


class ReviewEligibility(StrEnum):
    auto_eligible = "auto_eligible"
    human_required = "human_required"
    ineligible = "ineligible"


class ReviewRouteStatus(StrEnum):
    suggestion_ready = "suggestion_ready"
    pending_human = "pending_human"
    failed_safe = "failed_safe"


class MockBehavior(StrEnum):
    normal = "normal"
    low_confidence = "low_confidence"
    malformed = "malformed"
    provider_failure = "provider_failure"


class ReviewError(ValueError):
    """Base error for reviewer and schema failures."""


class ReviewSchemaError(ReviewError):
    """Provider output could not be validated; the payload must not be used."""


class ReviewerError(ReviewError):
    """The provider failed before a usable payload was produced."""


class PromptError(ReviewError):
    """Unknown prompt id or version."""


@dataclass(frozen=True)
class FindingView:
    """Deterministic observation, stripped of persistence concerns."""

    code: str
    severity: str
    message: str
    field: str | None = None
    row_number: int | None = None
    proposed_value: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "field": self.field,
            "row_number": self.row_number,
            "proposed_value": self.proposed_value,
        }

    @classmethod
    def from_finding(cls, finding: Finding) -> FindingView:
        return cls(
            code=finding.code,
            severity=finding.severity.value,
            message=finding.message,
            field=finding.field,
            row_number=finding.row_number,
            proposed_value=finding.proposed_value,
        )

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> FindingView:
        return cls(
            code=str(raw["code"]),
            severity=str(raw["severity"]),
            message=str(raw["message"]),
            field=_optional_str(raw.get("field")),
            row_number=_optional_int(raw.get("row_number")),
            proposed_value=_optional_str(raw.get("proposed_value")),
        )


@dataclass(frozen=True)
class CategorySuggestionInput:
    submitted_category: str
    description: str | None
    catalog_codes: tuple[str, ...]
    catalog_names: tuple[str, ...]
    findings: tuple[FindingView, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "submitted_category": self.submitted_category,
            "description": self.description,
            "catalog_codes": list(self.catalog_codes),
            "catalog_names": list(self.catalog_names),
            "findings": [item.to_dict() for item in self.findings],
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> CategorySuggestionInput:
        return cls(
            submitted_category=str(raw["submitted_category"]),
            description=_optional_str(raw.get("description")),
            catalog_codes=tuple(str(item) for item in raw.get("catalog_codes", ())),
            catalog_names=tuple(str(item) for item in raw.get("catalog_names", ())),
            findings=tuple(FindingView.from_dict(item) for item in raw.get("findings", ())),
        )


@dataclass(frozen=True)
class SupplierSummaryInput:
    supplier_code: str
    document_filename: str
    row_count: int
    findings: tuple[FindingView, ...]
    error_count: int
    warning_count: int
    info_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "supplier_code": self.supplier_code,
            "document_filename": self.document_filename,
            "row_count": self.row_count,
            "findings": [item.to_dict() for item in self.findings],
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "info_count": self.info_count,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> SupplierSummaryInput:
        findings = tuple(FindingView.from_dict(item) for item in raw.get("findings", ()))
        return cls(
            supplier_code=str(raw["supplier_code"]),
            document_filename=str(raw.get("document_filename", "")),
            row_count=int(raw.get("row_count", 0)),
            findings=findings,
            error_count=int(raw.get("error_count", 0)),
            warning_count=int(raw.get("warning_count", 0)),
            info_count=int(raw.get("info_count", 0)),
        )


@dataclass(frozen=True)
class ReconciliationExplanationInput:
    exception_code: str
    severity: str
    message: str
    expected_value: str
    actual_value: str
    financial_impact: Decimal
    purchase_order_number: str | None = None
    invoice_number: str | None = None
    product_sku: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "exception_code": self.exception_code,
            "severity": self.severity,
            "message": self.message,
            "expected_value": self.expected_value,
            "actual_value": self.actual_value,
            "financial_impact": str(self.financial_impact),
            "purchase_order_number": self.purchase_order_number,
            "invoice_number": self.invoice_number,
            "product_sku": self.product_sku,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> ReconciliationExplanationInput:
        return cls(
            exception_code=str(raw["exception_code"]),
            severity=str(raw["severity"]),
            message=str(raw["message"]),
            expected_value=str(raw["expected_value"]),
            actual_value=str(raw["actual_value"]),
            financial_impact=Decimal(str(raw["financial_impact"])),
            purchase_order_number=_optional_str(raw.get("purchase_order_number")),
            invoice_number=_optional_str(raw.get("invoice_number")),
            product_sku=_optional_str(raw.get("product_sku")),
        )

    @classmethod
    def from_exception(
        cls,
        item: ProposedException,
        *,
        purchase_order_number: str | None = None,
        invoice_number: str | None = None,
        product_sku: str | None = None,
    ) -> ReconciliationExplanationInput:
        return cls(
            exception_code=item.code,
            severity=item.severity.value,
            message=item.message,
            expected_value=item.expected_value,
            actual_value=item.actual_value,
            financial_impact=item.financial_impact,
            purchase_order_number=purchase_order_number,
            invoice_number=invoice_number,
            product_sku=product_sku,
        )


ReviewPayload = CategorySuggestionInput | SupplierSummaryInput | ReconciliationExplanationInput


@dataclass(frozen=True)
class ReviewRequest:
    """Provider-neutral input: a typed domain payload plus prompt coordinates."""

    review_type: ReviewType
    payload: ReviewPayload
    prompt_id: str
    prompt_version: str
    case_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "review_type": self.review_type.value,
            "payload": self.payload.to_dict(),
            "prompt_id": self.prompt_id,
            "prompt_version": self.prompt_version,
            "case_id": self.case_id,
        }


@dataclass(frozen=True)
class CategorySuggestion:
    submitted: str
    suggested_value: str
    confidence: float
    source: str


@dataclass(frozen=True)
class SupplierSheetContext:
    supplier_code: str
    filename: str
    rows: tuple[SupplierSheetRow, ...]
    findings: tuple[Finding, ...]
    catalog_codes: tuple[str, ...] = ()
    catalog_names: tuple[str, ...] = ()
    document_id: int | None = None


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _optional_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise TypeError(f"not an int: {value!r}")
    return int(value)
