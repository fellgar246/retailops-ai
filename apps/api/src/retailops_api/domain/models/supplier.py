from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from retailops_api.db.base import ActiveMixin, Base, IdMixin, TimestampMixin


class Supplier(IdMixin, ActiveMixin, TimestampMixin, Base):
    """A vendor RetailOps can buy from."""

    __tablename__ = "suppliers"

    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Stored verbatim as the supplier reports it: format and length vary by
    # jurisdiction (RFC, VAT, EIN), and no country-specific validation or
    # normalisation happens here. Not unique, because the same legal entity can
    # legitimately appear as more than one trading supplier, and because
    # correcting a mistyped tax ID must never be blocked by a constraint.
    tax_id: Mapped[str | None] = mapped_column(String(32), nullable=True)

    def __repr__(self) -> str:
        return f"Supplier(id={self.id!r}, code={self.code!r})"
