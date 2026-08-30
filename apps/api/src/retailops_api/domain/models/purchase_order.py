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
    from retailops_api.domain.models.store import Store
    from retailops_api.domain.models.supplier import Supplier


class PurchaseOrderStatus(StrEnum):
    """Lifecycle of an issued order.

    ``open`` is waiting for receipts. ``partial`` and ``received`` describe how
    much has arrived. ``closed`` is an operational finish. ``cancelled`` is
    excluded from reconciliation.
    """

    open = "open"
    partial = "partial"
    received = "received"
    closed = "closed"
    cancelled = "cancelled"


_PO_STATUSES = ", ".join(f"'{item.value}'" for item in PurchaseOrderStatus)


class PurchaseOrder(IdMixin, ActiveMixin, TimestampMixin, Base):
    """An order placed with one supplier for one store.

    ``po_number`` is unique per supplier: two vendors may reuse the same
    number, but one supplier cannot issue it twice. Money is ``NUMERIC(12, 4)``.
    Quantities on the lines are integers. Currency is a three-letter code
    stored on the header so every line shares it.
    """

    __tablename__ = "purchase_orders"
    __table_args__ = (
        UniqueConstraint("supplier_id", "po_number"),
        CheckConstraint(f"status IN ({_PO_STATUSES})", name="status_known"),
        CheckConstraint("length(currency) = 3", name="currency_iso"),
    )

    supplier_id: Mapped[int] = mapped_column(
        IdType, ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    store_id: Mapped[int] = mapped_column(
        IdType, ForeignKey("stores.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    po_number: Mapped[str] = mapped_column(String(50), nullable=False)
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    expected_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default=text("'MXN'"))
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'open'"), index=True
    )

    supplier: Mapped[Supplier] = relationship()
    store: Mapped[Store] = relationship()
    lines: Mapped[list[PurchaseOrderLine]] = relationship(
        back_populates="purchase_order",
        cascade="all, delete-orphan",
        order_by="PurchaseOrderLine.line_number",
    )

    def __repr__(self) -> str:
        return (
            f"PurchaseOrder(id={self.id!r}, supplier_id={self.supplier_id!r}, "
            f"po_number={self.po_number!r})"
        )


class PurchaseOrderLine(IdMixin, ActiveMixin, TimestampMixin, Base):
    """One ordered product on a purchase order.

    ``line_number`` is unique within the order. The same product may appear on
    more than one line; matching that case is ambiguous and must not guess.
    ``tax_rate`` is a percentage (16 means 16%). ``line_total`` is stored so
    a broken total can be detected rather than recomputed silently.
    """

    __tablename__ = "purchase_order_lines"
    __table_args__ = (
        UniqueConstraint("purchase_order_id", "line_number"),
        CheckConstraint("line_number > 0", name="line_number_positive"),
        CheckConstraint("ordered_quantity > 0", name="ordered_quantity_positive"),
        CheckConstraint("unit_cost >= 0", name="unit_cost_non_negative"),
        CheckConstraint("tax_rate >= 0", name="tax_rate_non_negative"),
        CheckConstraint("tax_amount >= 0", name="tax_amount_non_negative"),
        CheckConstraint("line_total >= 0", name="line_total_non_negative"),
    )

    purchase_order_id: Mapped[int] = mapped_column(
        IdType,
        ForeignKey("purchase_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[int] = mapped_column(
        IdType, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    ordered_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Money, nullable=False)
    tax_rate: Mapped[Decimal] = mapped_column(Money, nullable=False, server_default=text("0"))
    tax_amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Money, nullable=False)

    purchase_order: Mapped[PurchaseOrder] = relationship(back_populates="lines")
    product: Mapped[Product] = relationship()

    def __repr__(self) -> str:
        return (
            f"PurchaseOrderLine(purchase_order_id={self.purchase_order_id!r}, "
            f"line_number={self.line_number!r})"
        )
