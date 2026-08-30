from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from retailops_api.db.base import ActiveMixin, Base, IdMixin, TimestampMixin


class Store(IdMixin, ActiveMixin, TimestampMixin, Base):
    """A selling location. ``region`` and ``store_type`` group stores for forecasting."""

    __tablename__ = "stores"

    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    region: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    store_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    def __repr__(self) -> str:
        return f"Store(id={self.id!r}, code={self.code!r})"
