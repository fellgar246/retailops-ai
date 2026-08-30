"""Canonical supplier-sheet columns and header / cell normalisation.

A supplier offer line is one row with these fields:

- supplier_sku
- ean
- description
- category
- cost
- vat
- case_pack
- minimum_order_quantity
- lead_time_days

Incoming headers are folded to a stable token (lowercase, punctuation
collapsed) and mapped through aliases. Unknown columns are ignored.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation

from retailops_api.dataset.contract import quantize_money

SHEET_COLUMNS = (
    "supplier_sku",
    "ean",
    "description",
    "category",
    "cost",
    "vat",
    "case_pack",
    "minimum_order_quantity",
    "lead_time_days",
)

TEXT_COLUMNS = frozenset({"supplier_sku", "ean", "description", "category"})
DECIMAL_COLUMNS = frozenset({"cost", "vat"})
INTEGER_COLUMNS = frozenset({"case_pack", "minimum_order_quantity", "lead_time_days"})

_HEADER_ALIASES: dict[str, str] = {
    "supplier_sku": "supplier_sku",
    "supplier sku": "supplier_sku",
    "supplier sku code": "supplier_sku",
    "sku": "supplier_sku",
    "item sku": "supplier_sku",
    "ean": "ean",
    "ean13": "ean",
    "ean 13": "ean",
    "barcode": "ean",
    "gtin": "ean",
    "upc": "ean",
    "description": "description",
    "desc": "description",
    "product name": "description",
    "product": "description",
    "name": "description",
    "item description": "description",
    "category": "category",
    "cat": "category",
    "category code": "category",
    "merchandise category": "category",
    "cost": "cost",
    "unit cost": "cost",
    "cost price": "cost",
    "unit price": "cost",
    "price": "cost",
    "vat": "vat",
    "iva": "vat",
    "tax": "vat",
    "vat rate": "vat",
    "tax rate": "vat",
    "case_pack": "case_pack",
    "case pack": "case_pack",
    "pack size": "case_pack",
    "units per case": "case_pack",
    "pack": "case_pack",
    "minimum_order_quantity": "minimum_order_quantity",
    "minimum order quantity": "minimum_order_quantity",
    "minimum order": "minimum_order_quantity",
    "min order": "minimum_order_quantity",
    "min order qty": "minimum_order_quantity",
    "moq": "minimum_order_quantity",
    "lead_time_days": "lead_time_days",
    "lead time days": "lead_time_days",
    "lead time": "lead_time_days",
    "leadtime": "lead_time_days",
    "lt": "lead_time_days",
}

_PUNCT = re.compile(r"[_\-/]+")
_SPACES = re.compile(r"\s+")
_CURRENCY = re.compile(r"[$€£]|usd|mxn|eur", re.IGNORECASE)
_THOUSANDS = re.compile(r"^(\d{1,3})(,\d{3})+(\.\d+)?$")


def fold_header(raw: str) -> str:
    """Collapse a header cell to the token used for alias lookup."""
    token = raw.strip().casefold()
    token = _PUNCT.sub(" ", token)
    token = _SPACES.sub(" ", token).strip()
    return token


def map_header(raw: str) -> str | None:
    """Return the canonical column for ``raw``, or ``None`` when unknown."""
    return _HEADER_ALIASES.get(fold_header(raw))


def map_headers(headers: list[str]) -> dict[int, str]:
    """Map 0-based header indexes to canonical names.

    The first occurrence of a canonical name wins. Duplicates are ignored so
    a sheet that repeats ``SKU`` does not silently overwrite the first column.
    """
    mapping: dict[int, str] = {}
    seen: set[str] = set()
    for index, header in enumerate(headers):
        canonical = map_header(header)
        if canonical is None or canonical in seen:
            continue
        mapping[index] = canonical
        seen.add(canonical)
    return mapping


def blank_to_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def parse_decimal(raw: str) -> Decimal:
    """Parse a cost or VAT cell.

    Accepts a leading currency symbol, an optional trailing ``%``, and
    thousands separators when they look like ``1,234.56``. The decimal
    separator is ``.``.
    """
    text = raw.strip()
    text = _CURRENCY.sub("", text).strip()
    if text.endswith("%"):
        text = text[:-1].strip()
    text = text.replace(" ", "")
    if _THOUSANDS.fullmatch(text):
        text = text.replace(",", "")
    if not text:
        raise InvalidOperation("empty decimal")
    return Decimal(text)


def parse_int(raw: str) -> int:
    text = raw.strip().replace(" ", "")
    if _THOUSANDS.fullmatch(text):
        text = text.replace(",", "")
    if not text or "." in text:
        raise ValueError(f"not a whole number: {raw!r}")
    return int(text)


def format_money(value: Decimal) -> str:
    return str(quantize_money(value))


def format_decimal(value: Decimal) -> str:
    """Render a VAT rate without trailing zeros beyond what was stored."""
    normalized = value.normalize() if value == value.to_integral() else value
    if normalized == normalized.to_integral():
        return str(int(normalized))
    return format(normalized, "f")


def cell_values(headers: Mapping[int, str], cells: list[object]) -> dict[str, str | None]:
    """Project a physical row onto the canonical columns that were present."""
    values: dict[str, str | None] = dict.fromkeys(SHEET_COLUMNS)
    for index, name in headers.items():
        if index >= len(cells):
            continue
        values[name] = blank_to_none(cells[index])
    return values
