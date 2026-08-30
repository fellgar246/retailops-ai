from decimal import Decimal

import pytest

from retailops_api.documents.schema import (
    map_header,
    map_headers,
    parse_decimal,
    parse_int,
)


@pytest.mark.parametrize(
    ("raw", "canonical"),
    [
        ("Supplier SKU", "supplier_sku"),
        ("SKU", "supplier_sku"),
        ("Barcode", "ean"),
        ("EAN-13", "ean"),
        ("Product Name", "description"),
        ("IVA", "vat"),
        ("MOQ", "minimum_order_quantity"),
        ("Lead Time Days", "lead_time_days"),
        ("Units per case", "case_pack"),
        ("Unit Cost", "cost"),
        ("unknown-column", None),
    ],
)
def test_header_aliases_fold_to_canonical_names(raw: str, canonical: str | None) -> None:
    assert map_header(raw) == canonical


def test_first_canonical_column_wins_on_duplicate_headers() -> None:
    mapping = map_headers(["SKU", "Other", "sku"])

    assert mapping == {0: "supplier_sku"}


def test_decimal_parsing_accepts_currency_percent_and_thousands() -> None:
    assert parse_decimal("$1,234.50") == Decimal("1234.50")
    assert parse_decimal("16%") == Decimal("16")
    assert parse_decimal("  7.4500 ") == Decimal("7.4500")


def test_integer_parsing_rejects_fractions() -> None:
    assert parse_int("24") == 24
    with pytest.raises(ValueError):
        parse_int("12.5")
