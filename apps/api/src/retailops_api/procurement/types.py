"""In-memory shapes for three-way matching.

Persistence models live under ``retailops_api.domain.models``. These
dataclasses are what the matcher and the rules see.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from retailops_api.dataset.contract import MONEY_QUANT
from retailops_api.domain.models.reconciliation import ExceptionSeverity

DEFAULT_QUANTITY_TOLERANCE = 0
DEFAULT_MONETARY_TOLERANCE = Decimal("0.0000")
DEFAULT_PRICE_PERCENT_TOLERANCE = Decimal("0.0000")

UNMATCHED_PURCHASE_ORDER = "unmatched_purchase_order"
AMBIGUOUS_LINE = "ambiguous_line"
UNMATCHED_LINE = "unmatched_line"
SHORT_RECEIPT = "short_receipt"
OVER_RECEIPT = "over_receipt"
OVER_INVOICE = "over_invoice"
UNDER_INVOICE = "under_invoice"
INVOICE_WITHOUT_RECEIPT = "invoice_without_receipt"
COST_MISMATCH = "cost_mismatch"
LINE_TOTAL_MISMATCH = "line_total_mismatch"
UNEXPECTED_TAX = "unexpected_tax"
CURRENCY_MISMATCH = "currency_mismatch"

SEVERITY_BY_CODE: dict[str, ExceptionSeverity] = {
    UNMATCHED_PURCHASE_ORDER: ExceptionSeverity.error,
    AMBIGUOUS_LINE: ExceptionSeverity.error,
    UNMATCHED_LINE: ExceptionSeverity.error,
    SHORT_RECEIPT: ExceptionSeverity.warning,
    OVER_RECEIPT: ExceptionSeverity.warning,
    OVER_INVOICE: ExceptionSeverity.error,
    UNDER_INVOICE: ExceptionSeverity.warning,
    INVOICE_WITHOUT_RECEIPT: ExceptionSeverity.error,
    COST_MISMATCH: ExceptionSeverity.error,
    LINE_TOTAL_MISMATCH: ExceptionSeverity.error,
    UNEXPECTED_TAX: ExceptionSeverity.warning,
    CURRENCY_MISMATCH: ExceptionSeverity.error,
}


class ReconciliationError(ValueError):
    """The run cannot start: unknown supplier, missing document, cancelled scope."""


@dataclass(frozen=True)
class ReconciliationTolerances:
    """Explicit defaults: any difference is an exception unless a value is raised.

    Quantity is compared in whole units. Money uses the stored scale
    (four decimal places). Price percent is a percentage of the PO unit cost
    (``1`` means one percent). A price difference passes when it is within
    the monetary tolerance *or* the percent tolerance.
    """

    quantity_tolerance: int = DEFAULT_QUANTITY_TOLERANCE
    monetary_tolerance: Decimal = DEFAULT_MONETARY_TOLERANCE
    price_percent_tolerance: Decimal = DEFAULT_PRICE_PERCENT_TOLERANCE

    def __post_init__(self) -> None:
        if self.quantity_tolerance < 0:
            raise ValueError("quantity_tolerance must be >= 0")
        if self.monetary_tolerance < 0:
            raise ValueError("monetary_tolerance must be >= 0")
        if self.price_percent_tolerance < 0:
            raise ValueError("price_percent_tolerance must be >= 0")
        object.__setattr__(
            self, "monetary_tolerance", self.monetary_tolerance.quantize(MONEY_QUANT)
        )
        object.__setattr__(
            self, "price_percent_tolerance", self.price_percent_tolerance.quantize(MONEY_QUANT)
        )

    def to_dict(self) -> dict[str, str | int]:
        return {
            "quantity_tolerance": self.quantity_tolerance,
            "monetary_tolerance": str(self.monetary_tolerance),
            "price_percent_tolerance": str(self.price_percent_tolerance),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, object]) -> ReconciliationTolerances:
        return cls(
            quantity_tolerance=int(str(raw.get("quantity_tolerance", DEFAULT_QUANTITY_TOLERANCE))),
            monetary_tolerance=Decimal(
                str(raw.get("monetary_tolerance", DEFAULT_MONETARY_TOLERANCE))
            ),
            price_percent_tolerance=Decimal(
                str(raw.get("price_percent_tolerance", DEFAULT_PRICE_PERCENT_TOLERANCE))
            ),
        )


@dataclass(frozen=True)
class ReconciliationScope:
    """Select a purchase order, or an invoice that should resolve to one."""

    supplier_code: str
    po_number: str | None = None
    invoice_number: str | None = None

    def __post_init__(self) -> None:
        if not self.po_number and not self.invoice_number:
            raise ReconciliationError("provide a purchase order number or an invoice number")


@dataclass(frozen=True)
class PurchaseOrderLineView:
    id: int
    line_number: int
    product_id: int
    ordered_quantity: int
    unit_cost: Decimal
    tax_rate: Decimal
    tax_amount: Decimal
    line_total: Decimal


@dataclass(frozen=True)
class PurchaseOrderView:
    id: int
    number: str
    supplier_id: int
    store_id: int
    currency: str
    status: str
    lines: tuple[PurchaseOrderLineView, ...]


@dataclass(frozen=True)
class GoodsReceiptLineView:
    id: int
    goods_receipt_id: int
    line_number: int
    product_id: int
    purchase_order_line_id: int | None
    received_quantity: int


@dataclass(frozen=True)
class GoodsReceiptView:
    id: int
    number: str
    supplier_id: int
    purchase_order_id: int | None
    po_number: str | None
    status: str
    lines: tuple[GoodsReceiptLineView, ...]


@dataclass(frozen=True)
class SupplierInvoiceLineView:
    id: int
    supplier_invoice_id: int
    line_number: int
    product_id: int | None
    supplier_sku: str | None
    ean: str | None
    invoiced_quantity: int
    unit_cost: Decimal
    tax_rate: Decimal
    tax_amount: Decimal
    line_total: Decimal


@dataclass(frozen=True)
class SupplierInvoiceView:
    id: int
    number: str
    supplier_id: int
    purchase_order_id: int | None
    po_number: str | None
    currency: str
    status: str
    lines: tuple[SupplierInvoiceLineView, ...]


@dataclass(frozen=True)
class SelectedRecords:
    supplier_code: str
    supplier_id: int
    purchase_orders: tuple[PurchaseOrderView, ...]
    receipts: tuple[GoodsReceiptView, ...]
    invoices: tuple[SupplierInvoiceView, ...]


@dataclass(frozen=True)
class IdentityIndex:
    """Catalog lookups used after an exact product id has been ruled out."""

    product_ids_by_ean: dict[str, int]
    product_ids_by_supplier_sku: dict[str, tuple[int, ...]]

    def product_id_for_ean(self, ean: str) -> int | None:
        return self.product_ids_by_ean.get(ean)

    def product_ids_for_supplier_sku(self, supplier_sku: str) -> tuple[int, ...]:
        return self.product_ids_by_supplier_sku.get(supplier_sku, ())


@dataclass(frozen=True)
class ProposedException:
    code: str
    severity: ExceptionSeverity
    message: str
    expected_value: str
    actual_value: str
    financial_impact: Decimal
    purchase_order_id: int | None = None
    purchase_order_line_id: int | None = None
    goods_receipt_id: int | None = None
    goods_receipt_line_id: int | None = None
    supplier_invoice_id: int | None = None
    supplier_invoice_line_id: int | None = None
    product_id: int | None = None


@dataclass(frozen=True)
class ReconciliationDraft:
    exceptions: tuple[ProposedException, ...]
    purchase_order_ids: tuple[int, ...]
    goods_receipt_ids: tuple[int, ...]
    supplier_invoice_ids: tuple[int, ...]
    tolerances: ReconciliationTolerances


@dataclass(frozen=True)
class ReconciliationResult:
    run_id: int
    scope_key: str
    version: int
    reused: bool
    input_fingerprint: str
    purchase_order_count: int
    goods_receipt_count: int
    supplier_invoice_count: int
    exception_count: int
    error_count: int
    warning_count: int
    info_count: int
    total_financial_impact: Decimal
    exceptions: tuple[ProposedException, ...]
