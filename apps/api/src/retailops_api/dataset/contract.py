"""The portable retail dataset: tables, columns, keys, units and formats.

A dataset is a set of CSV files that use business codes, not database
surrogate ids. Ingestion resolves those codes to foreign keys.

Formats that every writer and reader must follow:

- Dates are ISO-8601 calendar days (``YYYY-MM-DD``). They are trading days,
  not timestamps, so they never carry a time or a timezone.
- Money (``cost``, ``unit_price``, ``discount_amount``) is a decimal with
  exactly four places after the point, matching ``NUMERIC(12, 4)``. The
  thousands separator is never used. The decimal separator is ``.``.
- Integers (quantities, case packs, lead times) have no fractional part.
- Booleans are the lowercase literals ``true`` and ``false``.
- Absent optional values are an empty field, not the strings ``null`` or
  ``None``.
- Text identifiers are stored verbatim; they are case-sensitive.

Natural keys (must be unique within each table):

- categories: ``code``
- products: ``sku``
- suppliers: ``code``
- supplier_products: ``(supplier_code, product_sku)``
- stores: ``code``
- daily_sales: ``(store_code, product_sku, business_date)``
- calendar: ``business_date``

Identifier shapes:

- category ``code``: ``^[A-Z][A-Z0-9-]{0,49}$``
- product ``sku``: ``^SKU-[0-9]{4,}$``
- supplier ``code``: ``^SUP-[A-Z0-9]+$``
- store ``code``: ``^ST-[0-9]{3,}$``
- ``ean``, when present: 8 to 14 digits
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from retailops_api.db.base import MONEY_SCALE

MONEY_QUANT = Decimal(10) ** -MONEY_SCALE

CATEGORY_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9-]{0,49}$")
PRODUCT_SKU_PATTERN = re.compile(r"^SKU-[0-9]{4,}$")
SUPPLIER_CODE_PATTERN = re.compile(r"^SUP-[A-Z0-9]+$")
STORE_CODE_PATTERN = re.compile(r"^ST-[0-9]{3,}$")
EAN_PATTERN = re.compile(r"^\d{8,14}$")

CATEGORY_COLUMNS = ("code", "name", "parent_code", "active")
PRODUCT_COLUMNS = ("sku", "name", "description", "ean", "category_code", "active")
SUPPLIER_COLUMNS = ("code", "name", "tax_id", "active")
SUPPLIER_PRODUCT_COLUMNS = (
    "supplier_code",
    "product_sku",
    "supplier_sku",
    "cost",
    "case_pack",
    "minimum_order_quantity",
    "lead_time_days",
    "active",
)
STORE_COLUMNS = ("code", "name", "region", "store_type", "active")
SALES_COLUMNS = (
    "store_code",
    "product_sku",
    "business_date",
    "units_sold",
    "unit_price",
    "discount_amount",
    "promotion",
    "stock_on_hand",
)
CALENDAR_COLUMNS = (
    "business_date",
    "weekday",
    "weekday_name",
    "is_weekend",
    "is_month_start",
    "is_month_end",
    "is_mid_month",
    "is_christmas",
    "is_new_year",
    "is_buen_fin",
    "is_holiday",
    "demand_multiplier",
)

WEEKDAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def quantize_money(value: Decimal) -> Decimal:
    """Round a monetary amount to the scale the database stores."""
    return value.quantize(MONEY_QUANT)


@dataclass(frozen=True)
class CategoryRow:
    """One node in the merchandise hierarchy. ``parent_code`` is empty for a root."""

    code: str
    name: str
    parent_code: str | None = None
    active: bool = True


@dataclass(frozen=True)
class ProductRow:
    """A sellable item, keyed by SKU and classified by category ``code``."""

    sku: str
    name: str
    category_code: str
    ean: str | None = None
    description: str | None = None
    active: bool = True


@dataclass(frozen=True)
class SupplierRow:
    """A vendor. ``tax_id`` is stored verbatim and may be absent."""

    code: str
    name: str
    tax_id: str | None = None
    active: bool = True


@dataclass(frozen=True)
class SupplierProductRow:
    """Commercial terms for one supplier offering one product.

    ``cost`` is a unit cost in the dataset currency, four decimal places.
    ``case_pack`` is units per case and must be at least 1.
    ``minimum_order_quantity`` and ``lead_time_days`` are non-negative integers;
    lead time is in whole days.
    """

    supplier_code: str
    product_sku: str
    cost: Decimal
    case_pack: int
    minimum_order_quantity: int
    lead_time_days: int
    supplier_sku: str | None = None
    active: bool = True


@dataclass(frozen=True)
class StoreRow:
    """A selling location. ``region`` and ``store_type`` group stores for modelling."""

    code: str
    name: str
    region: str
    store_type: str
    active: bool = True


@dataclass(frozen=True)
class SalesRow:
    """Daily sales and closing stock for one product in one store.

    ``unit_price`` is the per-unit price charged that day.
    ``discount_amount`` is the per-unit promotional discount (zero when not
    on promotion). The regular price is ``unit_price + discount_amount``.
    ``stock_on_hand`` is the closing units after the day's sales.
    """

    store_code: str
    product_sku: str
    business_date: date
    units_sold: int
    unit_price: Decimal
    discount_amount: Decimal
    promotion: bool
    stock_on_hand: int


@dataclass(frozen=True)
class CalendarDay:
    """One trading day's calendar attributes, reusable as modelling features.

    ``weekday`` is Monday=0 … Sunday=6, matching ``datetime.date.weekday``.
    ``demand_multiplier`` is the combined calendar effect for that day
    (weekends, month boundaries, Christmas, New Year, Buen Fin, holidays).
    """

    business_date: date
    weekday: int
    weekday_name: str
    is_weekend: bool
    is_month_start: bool
    is_month_end: bool
    is_mid_month: bool
    is_christmas: bool
    is_new_year: bool
    is_buen_fin: bool
    is_holiday: bool
    demand_multiplier: float


@dataclass(frozen=True)
class Catalog:
    """The five catalog tables of a portable dataset."""

    categories: tuple[CategoryRow, ...]
    products: tuple[ProductRow, ...]
    suppliers: tuple[SupplierRow, ...]
    supplier_products: tuple[SupplierProductRow, ...]
    stores: tuple[StoreRow, ...]


@dataclass(frozen=True)
class Dataset:
    """A complete portable dataset: catalog, daily sales and calendar features."""

    catalog: Catalog
    sales: tuple[SalesRow, ...]
    calendar: tuple[CalendarDay, ...]
