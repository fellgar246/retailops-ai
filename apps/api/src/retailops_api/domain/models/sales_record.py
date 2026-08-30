from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    UniqueConstraint,
    false,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from retailops_api.db.base import Base, CreatedAtMixin, IdMixin, IdType, Money

if TYPE_CHECKING:
    from retailops_api.domain.models.product import Product
    from retailops_api.domain.models.store import Store


class SalesRecord(IdMixin, CreatedAtMixin, Base):
    """Daily sales and closing stock for one product in one store.

    The natural key is ``(store_id, product_id, business_date)``: one row per
    product per store per trading day. Corrections re-ingest the same key as an
    upsert rather than appending a second row, which is why the record carries
    no ``updated_at`` and no ``active`` flag. See ADR-002.
    """

    __tablename__ = "sales_records"
    __table_args__ = (
        UniqueConstraint("store_id", "product_id", "business_date"),
        CheckConstraint("units_sold >= 0", name="units_sold_non_negative"),
        CheckConstraint("unit_price >= 0", name="unit_price_non_negative"),
        CheckConstraint("discount_amount >= 0", name="discount_amount_non_negative"),
        CheckConstraint("stock_on_hand >= 0", name="stock_on_hand_non_negative"),
    )

    store_id: Mapped[int] = mapped_column(
        IdType, ForeignKey("stores.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        IdType, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    units_sold: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Money, nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(
        Money, nullable=False, server_default=text("0")
    )
    promotion: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=false(), default=False
    )
    stock_on_hand: Mapped[int] = mapped_column(Integer, nullable=False)

    store: Mapped[Store] = relationship()
    product: Mapped[Product] = relationship()

    def __repr__(self) -> str:
        return (
            f"SalesRecord(store_id={self.store_id!r}, product_id={self.product_id!r}, "
            f"business_date={self.business_date!r})"
        )
