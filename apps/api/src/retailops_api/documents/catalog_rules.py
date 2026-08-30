"""Compare a supplier sheet to the live catalog.

No model is involved. These rules flag identity collisions, a cost increase
against current terms, and a category that does not match the product the
barcode already belongs to.
"""

from __future__ import annotations

from collections.abc import Sequence

from retailops_api.documents.catalog import CatalogIndex, ProductRef, TermRef
from retailops_api.documents.schema import format_money
from retailops_api.documents.types import Finding, SupplierSheetRow
from retailops_api.domain.models.document import FindingSeverity

SUPPLIER_SKU_MAPPED_ELSEWHERE = "supplier_sku_mapped_elsewhere"
EAN_MATCHES_EXISTING = "ean_matches_existing_product"
COST_INCREASE = "cost_increase"
CATEGORY_MISMATCH = "category_mismatch"


def validate_against_catalog(
    rows: Sequence[SupplierSheetRow],
    index: CatalogIndex,
    *,
    supplier_id: int,
) -> list[Finding]:
    findings: list[Finding] = []
    for row in rows:
        findings.extend(rule_ean_matches_existing(row, index))
        findings.extend(rule_supplier_sku_mapped_elsewhere(row, index, supplier_id=supplier_id))
        findings.extend(rule_cost_increase(row, index, supplier_id=supplier_id))
        findings.extend(rule_category_mismatch(row, index))
    return findings


def rule_ean_matches_existing(row: SupplierSheetRow, index: CatalogIndex) -> list[Finding]:
    if not row.ean:
        return []
    product = index.product_for_ean(row.ean)
    if product is None:
        return []
    return [
        Finding(
            code=EAN_MATCHES_EXISTING,
            severity=FindingSeverity.info,
            message=f"ean {row.ean} already identifies product {product.sku} ({product.name})",
            field="ean",
            row_number=row.row_number,
            proposed_value=product.sku,
        )
    ]


def rule_supplier_sku_mapped_elsewhere(
    row: SupplierSheetRow,
    index: CatalogIndex,
    *,
    supplier_id: int,
) -> list[Finding]:
    if not row.supplier_sku:
        return []
    findings: list[Finding] = []
    for term in index.terms_for_supplier_sku(row.supplier_sku):
        if term.supplier_id != supplier_id:
            findings.append(
                Finding(
                    code=SUPPLIER_SKU_MAPPED_ELSEWHERE,
                    severity=FindingSeverity.info,
                    message=(
                        f"supplier_sku {row.supplier_sku!r} is already used by "
                        f"{term.supplier_code} for product {term.product.sku}"
                    ),
                    field="supplier_sku",
                    row_number=row.row_number,
                    proposed_value=term.product.sku,
                )
            )
            continue
        if _same_identity(row, term):
            continue
        findings.append(
            Finding(
                code=SUPPLIER_SKU_MAPPED_ELSEWHERE,
                severity=FindingSeverity.warning,
                message=(
                    f"supplier_sku {row.supplier_sku!r} already maps to product "
                    f"{term.product.sku} (ean {term.product.ean or 'none'})"
                ),
                field="supplier_sku",
                row_number=row.row_number,
                proposed_value=term.product.sku,
            )
        )
    return findings


def rule_cost_increase(
    row: SupplierSheetRow,
    index: CatalogIndex,
    *,
    supplier_id: int,
) -> list[Finding]:
    if row.cost is None:
        return []
    term = index.term_for_row(supplier_id=supplier_id, ean=row.ean, supplier_sku=row.supplier_sku)
    if term is None or row.cost <= term.cost:
        return []
    current = format_money(term.cost)
    return [
        Finding(
            code=COST_INCREASE,
            severity=FindingSeverity.warning,
            message=(
                f"cost {format_money(row.cost)} is higher than the current term "
                f"{current} for product {term.product.sku}"
            ),
            field="cost",
            row_number=row.row_number,
            proposed_value=current,
        )
    ]


def rule_category_mismatch(row: SupplierSheetRow, index: CatalogIndex) -> list[Finding]:
    if not row.ean or not row.category:
        return []
    product = index.product_for_ean(row.ean)
    if product is None or _category_matches(row.category, product):
        return []
    return [
        Finding(
            code=CATEGORY_MISMATCH,
            severity=FindingSeverity.warning,
            message=(
                f"category {row.category!r} does not match catalog "
                f"{product.category_code} ({product.category_name}) for {product.sku}"
            ),
            field="category",
            row_number=row.row_number,
            proposed_value=product.category_code,
        )
    ]


def _same_identity(row: SupplierSheetRow, term: TermRef) -> bool:
    """True when the sheet line is an update of the existing pairing."""
    if row.ean and term.product.ean:
        return row.ean == term.product.ean
    return not (row.ean and term.product.ean is None)


def _category_matches(submitted: str, product: ProductRef) -> bool:
    token = submitted.strip().casefold()
    return token == product.category_code.casefold() or token == product.category_name.casefold()
