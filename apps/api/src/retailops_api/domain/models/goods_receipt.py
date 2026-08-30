from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from retailops_api.db.base import ActiveMixin, Base, IdMixin, IdType, TimestampMixin

if TYPE_CHECKING:
    from retailops_api.domain.models.product import Product
    from retailops_api.domain.models.purchase_order import PurchaseOrder, PurchaseOrderLine
    from retailops_api.domain.models.supplier import Supplier


class GoodsReceiptStatus(StrEnum):
    """A posted receipt is stock that arrived. ``cancelled`` is ignored."""

    posted = "posted"
    cancelled = "cancelled"


_RECEIPT_STATUSES = ", ".join(f"'{item.value}'" for item in GoodsReceiptStatus)


class GoodsReceipt(IdMixin, ActiveMixin, TimestampMixin, Base):
    """A delivery from a supplier, optionally against a purchase order.

    Several receipts may reference the same order: that is how a partial
    delivery is recorded. ``receipt_number`` is unique per supplier.
    ``po_number`` is kept even when the foreign key is set so a receipt that
    arrived with only a number can still be matched.
    """

    __tablename__ = "goods_receipts"
    __table_args__ = (
        UniqueConstraint("supplier_id", "receipt_number"),
        CheckConstraint(f"status IN ({_RECEIPT_STATUSES})", name="status_known"),
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
    receipt_number: Mapped[str] = mapped_column(String(50), nullable=False)
    po_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    received_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'posted'"), index=True
    )

    supplier: Mapped[Supplier] = relationship()
    purchase_order: Mapped[PurchaseOrder | None] = relationship()
    lines: Mapped[list[GoodsReceiptLine]] = relationship(
        back_populates="goods_receipt",
        cascade="all, delete-orphan",
        order_by="GoodsReceiptLine.line_number",
    )

    def __repr__(self) -> str:
        return (
            f"GoodsReceipt(id={self.id!r}, supplier_id={self.supplier_id!r}, "
            f"receipt_number={self.receipt_number!r})"
        )


class GoodsReceiptLine(IdMixin, ActiveMixin, TimestampMixin, Base):
    """Quantity received of one product on one receipt.

    Receipts are quantity facts: they carry no money. ``purchase_order_line_id``
    is set when the warehouse already knows which order line arrived.
    """

    __tablename__ = "goods_receipt_lines"
    __table_args__ = (
        UniqueConstraint("goods_receipt_id", "line_number"),
        CheckConstraint("line_number > 0", name="line_number_positive"),
        CheckConstraint("received_quantity > 0", name="received_quantity_positive"),
    )

    goods_receipt_id: Mapped[int] = mapped_column(
        IdType,
        ForeignKey("goods_receipts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[int] = mapped_column(
        IdType, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    purchase_order_line_id: Mapped[int | None] = mapped_column(
        IdType,
        ForeignKey("purchase_order_lines.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    received_quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    goods_receipt: Mapped[GoodsReceipt] = relationship(back_populates="lines")
    product: Mapped[Product] = relationship()
    purchase_order_line: Mapped[PurchaseOrderLine | None] = relationship()

    def __repr__(self) -> str:
        return (
            f"GoodsReceiptLine(goods_receipt_id={self.goods_receipt_id!r}, "
            f"line_number={self.line_number!r})"
        )
