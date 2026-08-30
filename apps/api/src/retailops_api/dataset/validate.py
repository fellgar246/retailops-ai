"""Validate a portable dataset and produce actionable failures."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from retailops_api.dataset.contract import (
    CATEGORY_CODE_PATTERN,
    EAN_PATTERN,
    PRODUCT_SKU_PATTERN,
    STORE_CODE_PATTERN,
    SUPPLIER_CODE_PATTERN,
    Catalog,
    CategoryRow,
    Dataset,
    ProductRow,
    SalesRow,
    StoreRow,
    SupplierProductRow,
    SupplierRow,
)

_MAX_ISSUES_IN_MESSAGE = 40


@dataclass(frozen=True)
class ValidationIssue:
    """One concrete problem in a dataset, named so a human can fix the row."""

    table: str
    code: str
    message: str
    row_number: int = 0
    field: str | None = None
    natural_key: str | None = None


class DatasetValidationError(ValueError):
    """Raised when a dataset fails validation. ``issues`` is the full list."""

    def __init__(self, issues: Sequence[ValidationIssue]) -> None:
        self.issues = list(issues)
        super().__init__(self._format())

    def _format(self) -> str:
        count = len(self.issues)
        lines = [f"Dataset is invalid ({count} issue{'s' if count != 1 else ''}):"]
        for issue in self.issues[:_MAX_ISSUES_IN_MESSAGE]:
            location = f"{issue.table}"
            if issue.row_number:
                location += f" row {issue.row_number}"
            if issue.natural_key:
                location += f" ({issue.natural_key})"
            if issue.field:
                location += f" field {issue.field}"
            lines.append(f"  {location}: {issue.message}")
        remaining = count - _MAX_ISSUES_IN_MESSAGE
        if remaining > 0:
            lines.append(f"  … and {remaining} more")
        return "\n".join(lines)


def validate_dataset(dataset: Dataset) -> list[ValidationIssue]:
    """Return every problem found. An empty list means the dataset is usable."""
    issues = validate_catalog(dataset.catalog)
    issues.extend(_validate_sales(dataset.sales, dataset.catalog))
    issues.extend(_validate_calendar(dataset))
    return issues


def validate_catalog(catalog: Catalog) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    issues.extend(_validate_categories(catalog.categories))
    issues.extend(_validate_products(catalog.products, catalog.categories))
    issues.extend(_validate_suppliers(catalog.suppliers))
    issues.extend(_validate_supplier_products(catalog.supplier_products, catalog))
    issues.extend(_validate_stores(catalog.stores))
    return issues


def assert_valid(dataset: Dataset) -> None:
    issues = validate_dataset(dataset)
    if issues:
        raise DatasetValidationError(issues)


def _issue(
    table: str,
    code: str,
    message: str,
    *,
    row_number: int = 0,
    field: str | None = None,
    natural_key: str | None = None,
) -> ValidationIssue:
    return ValidationIssue(
        table=table,
        code=code,
        message=message,
        row_number=row_number,
        field=field,
        natural_key=natural_key,
    )


def _validate_categories(rows: Sequence[CategoryRow]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    codes = [row.code for row in rows]
    issues.extend(_duplicate_keys("categories", "code", codes))
    known = set(codes)
    for number, row in enumerate(rows, start=1):
        key = row.code
        if not CATEGORY_CODE_PATTERN.fullmatch(row.code):
            issues.append(
                _issue(
                    "categories",
                    "invalid_identifier",
                    f"code {row.code!r} must match {CATEGORY_CODE_PATTERN.pattern}",
                    row_number=number,
                    field="code",
                    natural_key=key,
                )
            )
        if not row.name:
            issues.append(
                _issue(
                    "categories",
                    "null_required",
                    "name is required",
                    row_number=number,
                    field="name",
                    natural_key=key,
                )
            )
        if row.parent_code == row.code:
            issues.append(
                _issue(
                    "categories",
                    "broken_reference",
                    "parent_code must not equal code",
                    row_number=number,
                    field="parent_code",
                    natural_key=key,
                )
            )
        elif row.parent_code is not None and row.parent_code not in known:
            issues.append(
                _issue(
                    "categories",
                    "broken_reference",
                    f"parent_code {row.parent_code!r} is not a category in this dataset",
                    row_number=number,
                    field="parent_code",
                    natural_key=key,
                )
            )
    issues.extend(_category_cycles(rows))
    return issues


def _category_cycles(rows: Sequence[CategoryRow]) -> list[ValidationIssue]:
    parent_of = {row.code: row.parent_code for row in rows}
    issues: list[ValidationIssue] = []
    for code in parent_of:
        seen: list[str] = []
        current: str | None = code
        while current is not None:
            if current in seen:
                issues.append(
                    _issue(
                        "categories",
                        "broken_reference",
                        f"category tree has a cycle involving {code!r}",
                        field="parent_code",
                        natural_key=code,
                    )
                )
                break
            seen.append(current)
            current = parent_of.get(current)
    return issues


def _validate_products(
    rows: Sequence[ProductRow], categories: Sequence[CategoryRow]
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    issues.extend(_duplicate_keys("products", "sku", [row.sku for row in rows]))
    category_codes = {row.code for row in categories}
    barcodes = [(row.ean, row.sku) for row in rows if row.ean is not None]
    seen_ean: dict[str, str] = {}
    for ean, sku in barcodes:
        if ean in seen_ean:
            issues.append(
                _issue(
                    "products",
                    "duplicate_key",
                    f"ean {ean!r} is used by both {seen_ean[ean]!r} and {sku!r}",
                    field="ean",
                    natural_key=sku,
                )
            )
        else:
            seen_ean[ean] = sku

    for number, row in enumerate(rows, start=1):
        if not PRODUCT_SKU_PATTERN.fullmatch(row.sku):
            issues.append(
                _issue(
                    "products",
                    "invalid_identifier",
                    f"sku {row.sku!r} must match {PRODUCT_SKU_PATTERN.pattern}",
                    row_number=number,
                    field="sku",
                    natural_key=row.sku,
                )
            )
        if not row.name:
            issues.append(
                _issue(
                    "products",
                    "null_required",
                    "name is required",
                    row_number=number,
                    field="name",
                    natural_key=row.sku,
                )
            )
        if row.category_code not in category_codes:
            issues.append(
                _issue(
                    "products",
                    "broken_reference",
                    f"category_code {row.category_code!r} is not a category in this dataset",
                    row_number=number,
                    field="category_code",
                    natural_key=row.sku,
                )
            )
        if row.ean is not None and not EAN_PATTERN.fullmatch(row.ean):
            issues.append(
                _issue(
                    "products",
                    "invalid_identifier",
                    f"ean {row.ean!r} must be 8 to 14 digits",
                    row_number=number,
                    field="ean",
                    natural_key=row.sku,
                )
            )
    return issues


def _validate_suppliers(rows: Sequence[SupplierRow]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    issues.extend(_duplicate_keys("suppliers", "code", [row.code for row in rows]))
    for number, row in enumerate(rows, start=1):
        if not SUPPLIER_CODE_PATTERN.fullmatch(row.code):
            issues.append(
                _issue(
                    "suppliers",
                    "invalid_identifier",
                    f"code {row.code!r} must match {SUPPLIER_CODE_PATTERN.pattern}",
                    row_number=number,
                    field="code",
                    natural_key=row.code,
                )
            )
        if not row.name:
            issues.append(
                _issue(
                    "suppliers",
                    "null_required",
                    "name is required",
                    row_number=number,
                    field="name",
                    natural_key=row.code,
                )
            )
    return issues


def _validate_supplier_products(
    rows: Sequence[SupplierProductRow], catalog: Catalog
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    keys = [(row.supplier_code, row.product_sku) for row in rows]
    issues.extend(
        _duplicate_keys(
            "supplier_products", "(supplier_code, product_sku)", [_key(k) for k in keys]
        )
    )
    suppliers = {row.code for row in catalog.suppliers}
    products = {row.sku for row in catalog.products}
    for number, row in enumerate(rows, start=1):
        key = f"{row.supplier_code}/{row.product_sku}"
        if row.supplier_code not in suppliers:
            issues.append(
                _issue(
                    "supplier_products",
                    "broken_reference",
                    f"supplier_code {row.supplier_code!r} is not a supplier in this dataset",
                    row_number=number,
                    field="supplier_code",
                    natural_key=key,
                )
            )
        if row.product_sku not in products:
            issues.append(
                _issue(
                    "supplier_products",
                    "broken_reference",
                    f"product_sku {row.product_sku!r} is not a product in this dataset",
                    row_number=number,
                    field="product_sku",
                    natural_key=key,
                )
            )
        if row.cost < 0:
            issues.append(
                _issue(
                    "supplier_products",
                    "negative_value",
                    f"cost {row.cost} must be >= 0",
                    row_number=number,
                    field="cost",
                    natural_key=key,
                )
            )
        if row.case_pack <= 0:
            issues.append(
                _issue(
                    "supplier_products",
                    "negative_value",
                    f"case_pack {row.case_pack} must be > 0",
                    row_number=number,
                    field="case_pack",
                    natural_key=key,
                )
            )
        if row.minimum_order_quantity < 0:
            issues.append(
                _issue(
                    "supplier_products",
                    "negative_value",
                    f"minimum_order_quantity {row.minimum_order_quantity} must be >= 0",
                    row_number=number,
                    field="minimum_order_quantity",
                    natural_key=key,
                )
            )
        if row.lead_time_days < 0:
            issues.append(
                _issue(
                    "supplier_products",
                    "negative_value",
                    f"lead_time_days {row.lead_time_days} must be >= 0",
                    row_number=number,
                    field="lead_time_days",
                    natural_key=key,
                )
            )
    covered = {row.product_sku for row in rows}
    for product in catalog.products:
        if product.sku not in covered:
            issues.append(
                _issue(
                    "supplier_products",
                    "broken_reference",
                    f"product {product.sku!r} has no supplier terms",
                    field="product_sku",
                    natural_key=product.sku,
                )
            )
    return issues


def _validate_stores(rows: Sequence[StoreRow]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    issues.extend(_duplicate_keys("stores", "code", [row.code for row in rows]))
    for number, row in enumerate(rows, start=1):
        if not STORE_CODE_PATTERN.fullmatch(row.code):
            issues.append(
                _issue(
                    "stores",
                    "invalid_identifier",
                    f"code {row.code!r} must match {STORE_CODE_PATTERN.pattern}",
                    row_number=number,
                    field="code",
                    natural_key=row.code,
                )
            )
        for field_name, value in (
            ("name", row.name),
            ("region", row.region),
            ("store_type", row.store_type),
        ):
            if not value:
                issues.append(
                    _issue(
                        "stores",
                        "null_required",
                        f"{field_name} is required",
                        row_number=number,
                        field=field_name,
                        natural_key=row.code,
                    )
                )
    return issues


def _validate_sales(rows: Sequence[SalesRow], catalog: Catalog) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    keys = [(row.store_code, row.product_sku, row.business_date.isoformat()) for row in rows]
    issues.extend(
        _duplicate_keys(
            "daily_sales",
            "(store_code, product_sku, business_date)",
            [_key(k) for k in keys],
        )
    )
    stores = {row.code for row in catalog.stores}
    products = {row.sku for row in catalog.products}
    for number, row in enumerate(rows, start=1):
        key = f"{row.store_code}/{row.product_sku}/{row.business_date.isoformat()}"
        if row.store_code not in stores:
            issues.append(
                _issue(
                    "daily_sales",
                    "broken_reference",
                    f"store_code {row.store_code!r} is not a store in this dataset",
                    row_number=number,
                    field="store_code",
                    natural_key=key,
                )
            )
        if row.product_sku not in products:
            issues.append(
                _issue(
                    "daily_sales",
                    "broken_reference",
                    f"product_sku {row.product_sku!r} is not a product in this dataset",
                    row_number=number,
                    field="product_sku",
                    natural_key=key,
                )
            )
        if not isinstance(row.business_date, date):
            issues.append(
                _issue(
                    "daily_sales",
                    "invalid_date",
                    f"business_date {row.business_date!r} is not a calendar date",
                    row_number=number,
                    field="business_date",
                    natural_key=key,
                )
            )
        for field_name, value in (
            ("units_sold", row.units_sold),
            ("unit_price", row.unit_price),
            ("discount_amount", row.discount_amount),
            ("stock_on_hand", row.stock_on_hand),
        ):
            if value < 0:
                issues.append(
                    _issue(
                        "daily_sales",
                        "negative_value",
                        f"{field_name} {value} must be >= 0",
                        row_number=number,
                        field=field_name,
                        natural_key=key,
                    )
                )
        if isinstance(row.unit_price, Decimal) and row.unit_price != row.unit_price.quantize(
            Decimal("0.0001")
        ):
            issues.append(
                _issue(
                    "daily_sales",
                    "invalid_identifier",
                    f"unit_price {row.unit_price} must have at most four decimal places",
                    row_number=number,
                    field="unit_price",
                    natural_key=key,
                )
            )
    return issues


def _validate_calendar(dataset: Dataset) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    dates = [day.business_date for day in dataset.calendar]
    issues.extend(_duplicate_keys("calendar", "business_date", [d.isoformat() for d in dates]))
    for number, day in enumerate(dataset.calendar, start=1):
        if day.demand_multiplier <= 0:
            issues.append(
                _issue(
                    "calendar",
                    "negative_value",
                    f"demand_multiplier {day.demand_multiplier} must be > 0",
                    row_number=number,
                    field="demand_multiplier",
                    natural_key=day.business_date.isoformat(),
                )
            )
        if day.weekday < 0 or day.weekday > 6:
            issues.append(
                _issue(
                    "calendar",
                    "invalid_date",
                    f"weekday {day.weekday} must be 0-6 (Monday-Sunday)",
                    row_number=number,
                    field="weekday",
                    natural_key=day.business_date.isoformat(),
                )
            )
    if dataset.calendar:
        known = set(dates)
        for number, row in enumerate(dataset.sales, start=1):
            if row.business_date not in known:
                issues.append(
                    _issue(
                        "daily_sales",
                        "invalid_date",
                        f"business_date {row.business_date.isoformat()} "
                        "is not in the calendar table",
                        row_number=number,
                        field="business_date",
                        natural_key=(
                            f"{row.store_code}/{row.product_sku}/{row.business_date.isoformat()}"
                        ),
                    )
                )
    return issues


def _duplicate_keys(table: str, field: str, values: Iterable[str]) -> list[ValidationIssue]:
    counts = Counter(values)
    return [
        _issue(
            table,
            "duplicate_key",
            f"natural key {field}={key!r} appears {count} times",
            field=field,
            natural_key=key,
        )
        for key, count in sorted(counts.items())
        if count > 1
    ]


def _key(parts: tuple[object, ...]) -> str:
    return "/".join(str(part) for part in parts)
