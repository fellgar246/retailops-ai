"""Read and write a portable dataset as CSV files, with a stable checksum."""

from __future__ import annotations

import csv
import hashlib
import json
from collections.abc import Callable, Iterable, Sequence
from dataclasses import asdict
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from retailops_api.dataset.contract import (
    CALENDAR_COLUMNS,
    CATEGORY_COLUMNS,
    PRODUCT_COLUMNS,
    SALES_COLUMNS,
    STORE_COLUMNS,
    SUPPLIER_COLUMNS,
    SUPPLIER_PRODUCT_COLUMNS,
    CalendarDay,
    Catalog,
    CategoryRow,
    Dataset,
    ProductRow,
    SalesRow,
    StoreRow,
    SupplierProductRow,
    SupplierRow,
    quantize_money,
)
from retailops_api.dataset.validate import DatasetValidationError, ValidationIssue

CATEGORIES_FILE = "categories.csv"
PRODUCTS_FILE = "products.csv"
SUPPLIERS_FILE = "suppliers.csv"
SUPPLIER_PRODUCTS_FILE = "supplier_products.csv"
STORES_FILE = "stores.csv"
SALES_FILE = "daily_sales.csv"
CALENDAR_FILE = "calendar.csv"
MANIFEST_FILE = "manifest.json"


def write_dataset(
    dataset: Dataset,
    directory: Path,
    *,
    extra_manifest: dict[str, Any] | None = None,
) -> str:
    """Write CSV files and a manifest. Returns the SHA-256 hex digest of the rows."""
    directory.mkdir(parents=True, exist_ok=True)
    checksum = dataset_checksum(dataset)
    _write_csv(
        directory / CATEGORIES_FILE,
        CATEGORY_COLUMNS,
        (_row_values(row, CATEGORY_COLUMNS) for row in dataset.catalog.categories),
    )
    _write_csv(
        directory / PRODUCTS_FILE,
        PRODUCT_COLUMNS,
        (_row_values(row, PRODUCT_COLUMNS) for row in dataset.catalog.products),
    )
    _write_csv(
        directory / SUPPLIERS_FILE,
        SUPPLIER_COLUMNS,
        (_row_values(row, SUPPLIER_COLUMNS) for row in dataset.catalog.suppliers),
    )
    _write_csv(
        directory / SUPPLIER_PRODUCTS_FILE,
        SUPPLIER_PRODUCT_COLUMNS,
        (_row_values(row, SUPPLIER_PRODUCT_COLUMNS) for row in dataset.catalog.supplier_products),
    )
    _write_csv(
        directory / STORES_FILE,
        STORE_COLUMNS,
        (_row_values(row, STORE_COLUMNS) for row in dataset.catalog.stores),
    )
    _write_csv(
        directory / SALES_FILE,
        SALES_COLUMNS,
        (_row_values(row, SALES_COLUMNS) for row in dataset.sales),
    )
    _write_csv(
        directory / CALENDAR_FILE,
        CALENDAR_COLUMNS,
        (_row_values(row, CALENDAR_COLUMNS) for row in dataset.calendar),
    )
    manifest = {
        "checksum": checksum,
        "row_counts": {
            "categories": len(dataset.catalog.categories),
            "products": len(dataset.catalog.products),
            "suppliers": len(dataset.catalog.suppliers),
            "supplier_products": len(dataset.catalog.supplier_products),
            "stores": len(dataset.catalog.stores),
            "daily_sales": len(dataset.sales),
            "calendar": len(dataset.calendar),
        },
    }
    if extra_manifest:
        manifest = {**extra_manifest, **manifest}
    (directory / MANIFEST_FILE).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return checksum


def load_dataset(directory: Path) -> Dataset:
    """Read the CSV snapshot. Missing files or columns become validation issues."""
    issues: list[ValidationIssue] = []
    categories = _read_rows(
        directory / CATEGORIES_FILE, CATEGORY_COLUMNS, _parse_category, "categories", issues
    )
    products = _read_rows(
        directory / PRODUCTS_FILE, PRODUCT_COLUMNS, _parse_product, "products", issues
    )
    suppliers = _read_rows(
        directory / SUPPLIERS_FILE, SUPPLIER_COLUMNS, _parse_supplier, "suppliers", issues
    )
    supplier_products = _read_rows(
        directory / SUPPLIER_PRODUCTS_FILE,
        SUPPLIER_PRODUCT_COLUMNS,
        _parse_supplier_product,
        "supplier_products",
        issues,
    )
    stores = _read_rows(directory / STORES_FILE, STORE_COLUMNS, _parse_store, "stores", issues)
    sales = _read_rows(directory / SALES_FILE, SALES_COLUMNS, _parse_sales, "daily_sales", issues)
    calendar = _read_rows(
        directory / CALENDAR_FILE, CALENDAR_COLUMNS, _parse_calendar, "calendar", issues
    )
    if issues:
        raise DatasetValidationError(issues)
    return Dataset(
        catalog=Catalog(
            categories=tuple(categories),
            products=tuple(products),
            suppliers=tuple(suppliers),
            supplier_products=tuple(supplier_products),
            stores=tuple(stores),
        ),
        sales=tuple(sales),
        calendar=tuple(calendar),
    )


def dataset_checksum(dataset: Dataset) -> str:
    """SHA-256 of the canonical CSV encoding of every table, in a fixed order."""
    hasher = hashlib.sha256()
    tables: list[tuple[Sequence[str], Iterable[tuple[str, ...]]]] = [
        (
            CATEGORY_COLUMNS,
            (
                _row_values(row, CATEGORY_COLUMNS)
                for row in _sorted_categories(dataset.catalog.categories)
            ),
        ),
        (
            PRODUCT_COLUMNS,
            (
                _row_values(row, PRODUCT_COLUMNS)
                for row in _sorted_products(dataset.catalog.products)
            ),
        ),
        (
            SUPPLIER_COLUMNS,
            (
                _row_values(row, SUPPLIER_COLUMNS)
                for row in _sorted_suppliers(dataset.catalog.suppliers)
            ),
        ),
        (
            SUPPLIER_PRODUCT_COLUMNS,
            (
                _row_values(row, SUPPLIER_PRODUCT_COLUMNS)
                for row in _sorted_supplier_products(dataset.catalog.supplier_products)
            ),
        ),
        (
            STORE_COLUMNS,
            (_row_values(row, STORE_COLUMNS) for row in _sorted_stores(dataset.catalog.stores)),
        ),
        (SALES_COLUMNS, (_row_values(row, SALES_COLUMNS) for row in _sorted_sales(dataset.sales))),
        (
            CALENDAR_COLUMNS,
            (_row_values(row, CALENDAR_COLUMNS) for row in _sorted_calendar(dataset.calendar)),
        ),
    ]
    for columns, rows in tables:
        hasher.update(",".join(columns).encode("utf-8"))
        hasher.update(b"\n")
        for values in rows:
            hasher.update(",".join(values).encode("utf-8"))
            hasher.update(b"\n")
    return hasher.hexdigest()


def _sorted_categories(rows: Sequence[CategoryRow]) -> list[CategoryRow]:
    return sorted(rows, key=lambda row: row.code)


def _sorted_products(rows: Sequence[ProductRow]) -> list[ProductRow]:
    return sorted(rows, key=lambda row: row.sku)


def _sorted_suppliers(rows: Sequence[SupplierRow]) -> list[SupplierRow]:
    return sorted(rows, key=lambda row: row.code)


def _sorted_supplier_products(rows: Sequence[SupplierProductRow]) -> list[SupplierProductRow]:
    return sorted(rows, key=lambda row: (row.supplier_code, row.product_sku))


def _sorted_stores(rows: Sequence[StoreRow]) -> list[StoreRow]:
    return sorted(rows, key=lambda row: row.code)


def _sorted_sales(rows: Sequence[SalesRow]) -> list[SalesRow]:
    return sorted(rows, key=lambda row: (row.store_code, row.product_sku, row.business_date))


def _sorted_calendar(rows: Sequence[CalendarDay]) -> list[CalendarDay]:
    return sorted(rows, key=lambda row: row.business_date)


def _row_values(row: Any, columns: Sequence[str]) -> tuple[str, ...]:
    data = asdict(row)
    return tuple(_format_value(data[column]) for column in columns)


def _format_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(quantize_money(value), "f")
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def _write_csv(path: Path, columns: Sequence[str], rows: Iterable[tuple[str, ...]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(columns)
        writer.writerows(rows)


def _read_rows[T](
    path: Path,
    columns: Sequence[str],
    parser: Callable[[dict[str, str]], T],
    table: str,
    issues: list[ValidationIssue],
) -> list[T]:
    if not path.is_file():
        issues.append(
            ValidationIssue(
                table=table,
                code="missing_column",
                message=f"file {path.name} is missing",
            )
        )
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            issues.append(
                ValidationIssue(
                    table=table,
                    code="missing_column",
                    message=f"{path.name} has no header row",
                )
            )
            return []
        missing = [column for column in columns if column not in reader.fieldnames]
        if missing:
            issues.append(
                ValidationIssue(
                    table=table,
                    code="missing_column",
                    message=f"{path.name} is missing required columns: {', '.join(missing)}",
                )
            )
            return []
        rows: list[T] = []
        for number, raw in enumerate(reader, start=1):
            try:
                rows.append(parser(raw))
            except ValueError as error:
                issues.append(
                    ValidationIssue(
                        table=table,
                        code="invalid_date"
                        if "date" in str(error).lower()
                        else "invalid_identifier",
                        message=str(error),
                        row_number=number,
                    )
                )
        return rows


def _parse_category(raw: dict[str, str]) -> CategoryRow:
    return CategoryRow(
        code=_required(raw, "code"),
        name=_required(raw, "name"),
        parent_code=_optional(raw, "parent_code"),
        active=_parse_bool(raw, "active"),
    )


def _parse_product(raw: dict[str, str]) -> ProductRow:
    return ProductRow(
        sku=_required(raw, "sku"),
        name=_required(raw, "name"),
        category_code=_required(raw, "category_code"),
        ean=_optional(raw, "ean"),
        description=_optional(raw, "description"),
        active=_parse_bool(raw, "active"),
    )


def _parse_supplier(raw: dict[str, str]) -> SupplierRow:
    return SupplierRow(
        code=_required(raw, "code"),
        name=_required(raw, "name"),
        tax_id=_optional(raw, "tax_id"),
        active=_parse_bool(raw, "active"),
    )


def _parse_supplier_product(raw: dict[str, str]) -> SupplierProductRow:
    return SupplierProductRow(
        supplier_code=_required(raw, "supplier_code"),
        product_sku=_required(raw, "product_sku"),
        supplier_sku=_optional(raw, "supplier_sku"),
        cost=_parse_decimal(raw, "cost"),
        case_pack=_parse_int(raw, "case_pack"),
        minimum_order_quantity=_parse_int(raw, "minimum_order_quantity"),
        lead_time_days=_parse_int(raw, "lead_time_days"),
        active=_parse_bool(raw, "active"),
    )


def _parse_store(raw: dict[str, str]) -> StoreRow:
    return StoreRow(
        code=_required(raw, "code"),
        name=_required(raw, "name"),
        region=_required(raw, "region"),
        store_type=_required(raw, "store_type"),
        active=_parse_bool(raw, "active"),
    )


def _parse_sales(raw: dict[str, str]) -> SalesRow:
    return SalesRow(
        store_code=_required(raw, "store_code"),
        product_sku=_required(raw, "product_sku"),
        business_date=_parse_date(raw, "business_date"),
        units_sold=_parse_int(raw, "units_sold"),
        unit_price=_parse_decimal(raw, "unit_price"),
        discount_amount=_parse_decimal(raw, "discount_amount"),
        promotion=_parse_bool(raw, "promotion"),
        stock_on_hand=_parse_int(raw, "stock_on_hand"),
    )


def _parse_calendar(raw: dict[str, str]) -> CalendarDay:
    return CalendarDay(
        business_date=_parse_date(raw, "business_date"),
        weekday=_parse_int(raw, "weekday"),
        weekday_name=_required(raw, "weekday_name"),
        is_weekend=_parse_bool(raw, "is_weekend"),
        is_month_start=_parse_bool(raw, "is_month_start"),
        is_month_end=_parse_bool(raw, "is_month_end"),
        is_mid_month=_parse_bool(raw, "is_mid_month"),
        is_christmas=_parse_bool(raw, "is_christmas"),
        is_new_year=_parse_bool(raw, "is_new_year"),
        is_buen_fin=_parse_bool(raw, "is_buen_fin"),
        is_holiday=_parse_bool(raw, "is_holiday"),
        demand_multiplier=round(float(_required(raw, "demand_multiplier")), 6),
    )


def _required(raw: dict[str, str], field: str) -> str:
    value = (raw.get(field) or "").strip()
    if not value:
        raise ValueError(f"{field} is required")
    return value


def _optional(raw: dict[str, str], field: str) -> str | None:
    value = (raw.get(field) or "").strip()
    return value or None


def _parse_bool(raw: dict[str, str], field: str) -> bool:
    value = (raw.get(field) or "").strip().lower()
    if value == "true":
        return True
    if value == "false":
        return False
    raise ValueError(f"{field} must be true or false, got {raw.get(field)!r}")


def _parse_int(raw: dict[str, str], field: str) -> int:
    value = (raw.get(field) or "").strip()
    try:
        return int(value)
    except ValueError as error:
        raise ValueError(f"{field} must be an integer, got {raw.get(field)!r}") from error


def _parse_decimal(raw: dict[str, str], field: str) -> Decimal:
    value = (raw.get(field) or "").strip()
    try:
        return quantize_money(Decimal(value))
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"{field} must be a decimal, got {raw.get(field)!r}") from error


def _parse_date(raw: dict[str, str], field: str) -> date:
    value = (raw.get(field) or "").strip()
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(
            f"{field} must be an ISO date (YYYY-MM-DD), got {raw.get(field)!r}"
        ) from error
