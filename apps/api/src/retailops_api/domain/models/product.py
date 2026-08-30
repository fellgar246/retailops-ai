from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from retailops_api.db.base import ActiveMixin, Base, IdMixin, IdType, TimestampMixin

if TYPE_CHECKING:
    from retailops_api.domain.models.category import Category


class Product(IdMixin, ActiveMixin, TimestampMixin, Base):
    """A sellable item. ``sku`` is the identifier the business uses day to day."""

    __tablename__ = "products"

    sku: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Nullable and unique: PostgreSQL treats NULLs as distinct, so products
    # without a barcode coexist while a present barcode stays unique.
    ean: Mapped[str | None] = mapped_column(String(14), nullable=True, unique=True)
    category_id: Mapped[int] = mapped_column(
        IdType,
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    category: Mapped[Category] = relationship()

    def __repr__(self) -> str:
        return f"Product(id={self.id!r}, sku={self.sku!r})"
