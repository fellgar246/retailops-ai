"""Deterministic intra-document rules for a supplier sheet.

Each rule is a plain function so it can be tested without storage or a
database. Cross-catalog checks live in ``catalog_rules``.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from retailops_api.dataset.contract import EAN_PATTERN
from retailops_api.documents.schema import format_decimal
from retailops_api.documents.types import Finding, RuleConfig, SupplierSheetRow
from retailops_api.domain.models.document import FindingSeverity

REQUIRED_FIELD = "required_field"
INVALID_EAN = "invalid_ean"
COST_NEGATIVE = "cost_negative"
INVALID_VAT = "invalid_vat"
CASE_PACK_NOT_POSITIVE = "case_pack_not_positive"
MOQ_NEGATIVE = "moq_negative"
LEAD_TIME_NEGATIVE = "lead_time_negative"
DUPLICATE_SUPPLIER_SKU = "duplicate_supplier_sku"
DUPLICATE_EAN = "duplicate_ean"


def validate_sheet(
    rows: Sequence[SupplierSheetRow],
    *,
    config: RuleConfig | None = None,
) -> list[Finding]:
    settings = config or RuleConfig()
    findings: list[Finding] = []
    for row in rows:
        findings.extend(rule_required_fields(row, settings))
        findings.extend(rule_ean_format(row))
        findings.extend(rule_cost_non_negative(row))
        findings.extend(rule_vat_allowed(row, settings))
        findings.extend(rule_case_pack_positive(row))
        findings.extend(rule_moq_non_negative(row))
        findings.extend(rule_lead_time_non_negative(row))
    findings.extend(rule_duplicate_supplier_sku(rows))
    findings.extend(rule_duplicate_ean(rows))
    return findings


def rule_required_fields(row: SupplierSheetRow, config: RuleConfig) -> list[Finding]:
    findings: list[Finding] = []
    for name in config.required_fields:
        if name in row.invalid_fields:
            continue
        if getattr(row, name) is None:
            findings.append(
                Finding(
                    code=REQUIRED_FIELD,
                    severity=FindingSeverity.error,
                    message=f"{name} is required",
                    field=name,
                    row_number=row.row_number,
                )
            )
    return findings


def rule_ean_format(row: SupplierSheetRow) -> list[Finding]:
    if row.ean is None or "ean" in row.invalid_fields:
        return []
    if EAN_PATTERN.fullmatch(row.ean):
        return []
    return [
        Finding(
            code=INVALID_EAN,
            severity=FindingSeverity.error,
            message=f"ean {row.ean!r} must be 8 to 14 digits",
            field="ean",
            row_number=row.row_number,
        )
    ]


def rule_cost_non_negative(row: SupplierSheetRow) -> list[Finding]:
    if row.cost is None:
        return []
    if row.cost >= 0:
        return []
    return [
        Finding(
            code=COST_NEGATIVE,
            severity=FindingSeverity.error,
            message=f"cost {row.cost} must be >= 0",
            field="cost",
            row_number=row.row_number,
        )
    ]


def rule_vat_allowed(row: SupplierSheetRow, config: RuleConfig) -> list[Finding]:
    if row.vat is None:
        return []
    allowed = set(config.allowed_vat)
    if row.vat in allowed:
        return []
    listed = ", ".join(format_decimal(rate) for rate in config.allowed_vat)
    return [
        Finding(
            code=INVALID_VAT,
            severity=FindingSeverity.error,
            message=f"vat {format_decimal(row.vat)} is not an allowed rate ({listed})",
            field="vat",
            row_number=row.row_number,
        )
    ]


def rule_case_pack_positive(row: SupplierSheetRow) -> list[Finding]:
    if row.case_pack is None:
        return []
    if row.case_pack > 0:
        return []
    return [
        Finding(
            code=CASE_PACK_NOT_POSITIVE,
            severity=FindingSeverity.error,
            message=f"case_pack {row.case_pack} must be > 0",
            field="case_pack",
            row_number=row.row_number,
        )
    ]


def rule_moq_non_negative(row: SupplierSheetRow) -> list[Finding]:
    if row.minimum_order_quantity is None:
        return []
    if row.minimum_order_quantity >= 0:
        return []
    return [
        Finding(
            code=MOQ_NEGATIVE,
            severity=FindingSeverity.error,
            message=f"minimum_order_quantity {row.minimum_order_quantity} must be >= 0",
            field="minimum_order_quantity",
            row_number=row.row_number,
        )
    ]


def rule_lead_time_non_negative(row: SupplierSheetRow) -> list[Finding]:
    if row.lead_time_days is None:
        return []
    if row.lead_time_days >= 0:
        return []
    return [
        Finding(
            code=LEAD_TIME_NEGATIVE,
            severity=FindingSeverity.error,
            message=f"lead_time_days {row.lead_time_days} must be >= 0",
            field="lead_time_days",
            row_number=row.row_number,
        )
    ]


def rule_duplicate_supplier_sku(rows: Sequence[SupplierSheetRow]) -> list[Finding]:
    return _duplicates(
        field="supplier_sku",
        code=DUPLICATE_SUPPLIER_SKU,
        values=[(row.row_number, row.supplier_sku) for row in rows if row.supplier_sku],
    )


def rule_duplicate_ean(rows: Sequence[SupplierSheetRow]) -> list[Finding]:
    return _duplicates(
        field="ean",
        code=DUPLICATE_EAN,
        values=[(row.row_number, row.ean) for row in rows if row.ean],
    )


def _duplicates(
    *,
    field: str,
    code: str,
    values: list[tuple[int, str]],
) -> list[Finding]:
    grouped: dict[str, list[int]] = defaultdict(list)
    for row_number, value in values:
        grouped[value].append(row_number)
    findings: list[Finding] = []
    for value, numbers in grouped.items():
        if len(numbers) < 2:
            continue
        listed = ", ".join(str(number) for number in numbers)
        for row_number in numbers:
            findings.append(
                Finding(
                    code=code,
                    severity=FindingSeverity.error,
                    message=f"{field} {value!r} is repeated on rows {listed}",
                    field=field,
                    row_number=row_number,
                )
            )
    return findings
