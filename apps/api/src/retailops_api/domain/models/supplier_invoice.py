from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from retailops_api.db.base import ActiveMixin, Base, IdMixin, IdType, Money, TimestampMixin

if TYPE_CHECKING:
    from retailops_api.domain.models.product import Product
    from retailops_api.domain.models.purchase_order import PurchaseOrder
    from retailops_api.domain.models.supplier import Supplier


class SupplierInvoiceStatus(StrEnum):
    """How far an invoice has been processed.

    ``received`` is captured. ``matched`` and ``exception`` are operational
    outcomes after reconciliation. ``cancelled`` is excluded from matching.
    """

    received = "received"
    matched = "matched"
    exception = "exception"
    cancelled = "cancelled"


_INVOICE_STATUSES = ", ".join(f"'{item.value}'" for item in SupplierInvoiceStatus)


class SupplierInvoice(IdMixin, ActiveMixin, TimestampMixin, Base):
    """A supplier invoice, uniquely identified by supplier and invoice number.

    The same number from two suppliers is allowed. Repeating a number for one
    supplier is rejected so an obvious duplicate cannot be stored. The purchase
    order is optional: an invoice may arrive with only a PO number, or with
    neither, in which case matching records that it could not be placed.
    """

    __tablename__ = "supplier_invoices"
    __table_args__ = (
        UniqueConstraint("supplier_id", "invoice_number"),
        CheckConstraint(f"status IN ({_INVOICE_STATUSES})", name="status_known"),
        CheckConstraint("length(currency) = 3", name="currency_iso"),
    )

    supplier_id: Mapped[int] = mapped_column(
        IdType, ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    purchase_order_id: Mapped[int | None] = mapped_column(
        IdType,
        ForeignKey("purchase_orders.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    invoice_number: Mapped[str] = mapped_column(String(50), nullable=False)
    po_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default=text("'MXN'"))
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'received'"), index=True
    )

    supplier: Mapped[Supplier] = relationship()
    purchase_order: Mapped[PurchaseOrder | None] = relationship()
    lines: Mapped[list[SupplierInvoiceLine]] = relationship(
        back_populates="supplier_invoice",
        cascade="all, delete-orphan",
        order_by="SupplierInvoiceLine.line_number",
    )

    def __repr__(self) -> str:
        return (
            f"SupplierInvoice(id={self.id!r}, supplier_id={self.supplier_id!r}, "
            f"invoice_number={self.invoice_number!r})"
        )


class SupplierInvoiceLine(IdMixin, ActiveMixin, TimestampMixin, Base):
    """One invoiced product. Identity fields may be incomplete until matched.

    ``product_id`` is optional so a line that only carries a supplier SKU or
    EAN can still be stored. Matching then resolves identity; if more than one
    product fits, an exception is raised instead of picking one.
    """

    __tablename__ = "supplier_invoice_lines"
    __table_args__ = (
        UniqueConstraint("supplier_invoice_id", "line_number"),
        CheckConstraint("line_number > 0", name="line_number_positive"),
        CheckConstraint("invoiced_quantity > 0", name="invoiced_quantity_positive"),
        CheckConstraint("unit_cost >= 0", name="unit_cost_non_negative"),
        CheckConstraint("tax_rate >= 0", name="tax_rate_non_negative"),
        CheckConstraint("tax_amount >= 0", name="tax_amount_non_negative"),
        CheckConstraint("line_total >= 0", name="line_total_non_negative"),
    )

    supplier_invoice_id: Mapped[int] = mapped_column(
        IdType,
        ForeignKey("supplier_invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[int | None] = mapped_column(
        IdType, ForeignKey("products.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    supplier_sku: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ean: Mapped[str | None] = mapped_column(String(14), nullable=True)
    invoiced_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Money, nullable=False)
    tax_rate: Mapped[Decimal] = mapped_column(Money, nullable=False, server_default=text("0"))
    tax_amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Money, nullable=False)

    supplier_invoice: Mapped[SupplierInvoice] = relationship(back_populates="lines")
    product: Mapped[Product | None] = relationship()

    def __repr__(self) -> str:
        return (
            f"SupplierInvoiceLine(supplier_invoice_id={self.supplier_invoice_id!r}, "
            f"line_number={self.line_number!r})"
        )
