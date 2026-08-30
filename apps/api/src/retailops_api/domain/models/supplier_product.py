from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from retailops_api.db.base import ActiveMixin, Base, IdMixin, IdType, Money, TimestampMixin

if TYPE_CHECKING:
    from retailops_api.domain.models.product import Product
    from retailops_api.domain.models.supplier import Supplier


class SupplierProduct(IdMixin, ActiveMixin, TimestampMixin, Base):
    """Commercial terms under which one supplier offers one product."""

    __tablename__ = "supplier_products"
    __table_args__ = (
        UniqueConstraint("supplier_id", "product_id"),
        CheckConstraint("cost >= 0", name="cost_non_negative"),
        CheckConstraint("case_pack > 0", name="case_pack_positive"),
        CheckConstraint("minimum_order_quantity >= 0", name="min_order_qty_non_negative"),
        CheckConstraint("lead_time_days >= 0", name="lead_time_days_non_negative"),
    )

    supplier_id: Mapped[int] = mapped_column(
        IdType, ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        IdType, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    supplier_sku: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cost: Mapped[Decimal] = mapped_column(Money, nullable=False)
    case_pack: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    minimum_order_quantity: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    lead_time_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    supplier: Mapped[Supplier] = relationship()
    product: Mapped[Product] = relationship()

    def __repr__(self) -> str:
        return f"SupplierProduct(supplier_id={self.supplier_id!r}, product_id={self.product_id!r})"
