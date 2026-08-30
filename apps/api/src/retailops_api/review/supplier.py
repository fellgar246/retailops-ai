"""Optional semantic review on top of deterministic supplier findings.

The findings produced by sheet and catalog rules stay untouched. A reviewer
may classify uncertain category text, write a summary, prioritize and
suggest a next action. Nothing here writes the catalog or the document.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from retailops_api.documents.catalog_rules import CATEGORY_MISMATCH
from retailops_api.documents.types import Finding, ProcessResult, SupplierSheetRow
from retailops_api.review.contract import AIReviewer, SafeReview, build_request, review_safely
from retailops_api.review.routing import RoutingDecision, route
from retailops_api.review.schemas import ReviewResult
from retailops_api.review.types import (
    CategorySuggestion,
    CategorySuggestionInput,
    FindingView,
    RecommendedAction,
    ReviewType,
    SupplierSheetContext,
    SupplierSummaryInput,
)


@dataclass(frozen=True)
class SupplierSemanticReview:
    """Deterministic findings plus optional reviewer output and a route."""

    findings: tuple[Finding, ...]
    summary: str
    category_suggestions: tuple[CategorySuggestion, ...]
    recommended_action: RecommendedAction
    prioritization: tuple[str, ...]
    ai_result: ReviewResult | None
    routing: RoutingDecision
    attempts: tuple[SafeReview, ...]

    @property
    def source_of_truth(self) -> tuple[Finding, ...]:
        return self.findings


def review_supplier_sheet(
    context: SupplierSheetContext,
    reviewer: AIReviewer | None = None,
) -> SupplierSemanticReview:
    """Combine sheet findings with an optional reviewer. Findings are not edited."""

    findings = tuple(context.findings)
    views = tuple(FindingView.from_finding(item) for item in findings)
    error_count = sum(1 for item in findings if item.severity.value == "error")
    warning_count = sum(1 for item in findings if item.severity.value == "warning")
    info_count = sum(1 for item in findings if item.severity.value == "info")
    attempts: list[SafeReview] = []
    suggestions: list[CategorySuggestion] = []
    summary_result: ReviewResult | None = None

    if reviewer is not None:
        for payload in _category_payloads(context, views):
            request = build_request(
                ReviewType.category_suggestion,
                payload,
                case_id=_case_id("category", context, payload.submitted_category),
            )
            attempt = review_safely(reviewer, request)
            attempts.append(attempt)
            if attempt.result is not None and attempt.result.suggested_value:
                suggestions.append(
                    CategorySuggestion(
                        submitted=payload.submitted_category,
                        suggested_value=attempt.result.suggested_value,
                        confidence=attempt.result.confidence,
                        source="reviewer",
                    )
                )
        summary_request = build_request(
            ReviewType.supplier_summary,
            SupplierSummaryInput(
                supplier_code=context.supplier_code,
                document_filename=context.filename,
                row_count=len(context.rows),
                findings=views,
                error_count=error_count,
                warning_count=warning_count,
                info_count=info_count,
            ),
            case_id=_case_id("summary", context, context.filename),
        )
        summary_attempt = review_safely(reviewer, summary_request)
        attempts.append(summary_attempt)
        summary_result = summary_attempt.result

    primary = summary_result or _first_valid(attempts)
    failed = next((item for item in attempts if not item.ok), None)
    routing = route(
        primary,
        financial_impact=Decimal("0"),
        error=None if primary is not None else (failed.error if failed else None),
        source_error_count=error_count,
    )
    return SupplierSemanticReview(
        findings=findings,
        summary=_summary_text(findings, primary),
        category_suggestions=tuple(suggestions),
        recommended_action=_action(primary, error_count),
        prioritization=_prioritize(findings, primary),
        ai_result=primary,
        routing=routing,
        attempts=tuple(attempts),
    )


def review_from_process_result(
    result: ProcessResult,
    reviewer: AIReviewer | None = None,
    *,
    rows: Sequence[SupplierSheetRow] = (),
    catalog_codes: Sequence[str] = (),
    catalog_names: Sequence[str] = (),
) -> SupplierSemanticReview:
    return review_supplier_sheet(
        SupplierSheetContext(
            supplier_code=result.supplier_code,
            filename=result.filename,
            rows=tuple(rows),
            findings=result.findings,
            catalog_codes=tuple(catalog_codes),
            catalog_names=tuple(catalog_names),
            document_id=result.document_id,
        ),
        reviewer,
    )


def _category_payloads(
    context: SupplierSheetContext,
    views: tuple[FindingView, ...],
) -> list[CategorySuggestionInput]:
    submitted: list[str] = []
    for finding in context.findings:
        if finding.code == CATEGORY_MISMATCH and finding.field == "category":
            row = _row_at(context.rows, finding.row_number)
            text = row.category if row is not None and row.category else None
            if text and text not in submitted:
                submitted.append(text)
    for row in context.rows:
        if not row.category:
            continue
        if (
            context.catalog_codes
            and not _known_category(row.category, context)
            and row.category not in submitted
        ):
            submitted.append(row.category)
    return [
        CategorySuggestionInput(
            submitted_category=text,
            description=_description_for(context.rows, text),
            catalog_codes=context.catalog_codes,
            catalog_names=context.catalog_names,
            findings=tuple(item for item in views if item.field == "category"),
        )
        for text in submitted
    ]


def _known_category(submitted: str, context: SupplierSheetContext) -> bool:
    token = submitted.strip().casefold()
    codes = {item.casefold() for item in context.catalog_codes}
    names = {item.casefold() for item in context.catalog_names}
    return token in codes or token in names


def _row_at(rows: Sequence[SupplierSheetRow], row_number: int | None) -> SupplierSheetRow | None:
    if row_number is None:
        return None
    for row in rows:
        if row.row_number == row_number:
            return row
    return None


def _description_for(rows: Sequence[SupplierSheetRow], category: str) -> str | None:
    for row in rows:
        if row.category == category and row.description:
            return row.description
    return None


def _case_id(kind: str, context: SupplierSheetContext, suffix: str) -> str:
    document = context.document_id if context.document_id is not None else context.filename
    return f"{context.supplier_code}:{document}:{kind}:{suffix}"


def _first_valid(attempts: Sequence[SafeReview]) -> ReviewResult | None:
    for attempt in attempts:
        if attempt.result is not None:
            return attempt.result
    return None


def _summary_text(findings: Sequence[Finding], result: ReviewResult | None) -> str:
    if result is not None:
        return result.summary
    errors = sum(1 for item in findings if item.severity.value == "error")
    warnings = sum(1 for item in findings if item.severity.value == "warning")
    return f"{len(findings)} deterministic findings ({errors} error, {warnings} warning)"


def _action(result: ReviewResult | None, error_count: int) -> RecommendedAction:
    if error_count > 0:
        return RecommendedAction.request_correction
    if result is None:
        return RecommendedAction.human_review
    return result.recommended_action


def _prioritize(findings: Sequence[Finding], result: ReviewResult | None) -> tuple[str, ...]:
    rank = {"error": 0, "warning": 1, "info": 2}
    ordered = sorted(
        findings,
        key=lambda item: (rank.get(item.severity.value, 9), item.code, item.row_number or 0),
    )
    codes = tuple(item.code for item in ordered)
    if result is None:
        return codes
    hinted = tuple(item.code for item in result.findings if item.code)
    if not hinted:
        return codes
    seen = set(hinted)
    return hinted + tuple(code for code in codes if code not in seen)
