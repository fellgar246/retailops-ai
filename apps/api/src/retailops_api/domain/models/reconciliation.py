from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from retailops_api.db.base import (
    ActiveMixin,
    Base,
    CreatedAtMixin,
    IdMixin,
    IdType,
    Money,
    TimestampMixin,
)


class ExceptionSeverity(StrEnum):
    error = "error"
    warning = "warning"
    info = "info"


class ExceptionResolution(StrEnum):
    open = "open"
    resolved = "resolved"
    dismissed = "dismissed"


_SEVERITIES = ", ".join(f"'{item.value}'" for item in ExceptionSeverity)
_RESOLUTIONS = ", ".join(f"'{item.value}'" for item in ExceptionResolution)


class ReconciliationRun(IdMixin, CreatedAtMixin, Base):
    """One deterministic three-way match of a purchase-order scope.

    A run is an evaluation fact: the same inputs produce the same exceptions,
    and a second call with an unchanged fingerprint returns this row instead
    of writing another. When the documents or the tolerances change, a new
    run is stored with ``version`` incremented for that ``scope_key``.

    There is no ``updated_at`` and no ``active`` flag; an existing run is not
    edited. Exceptions belong to the run and are removed with it.
    """

    __tablename__ = "reconciliation_runs"
    __table_args__ = (
        UniqueConstraint("scope_key", "version"),
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint("exception_count >= 0", name="exception_count_non_negative"),
        CheckConstraint("error_count >= 0", name="error_count_non_negative"),
        CheckConstraint("warning_count >= 0", name="warning_count_non_negative"),
        CheckConstraint("info_count >= 0", name="info_count_non_negative"),
        CheckConstraint("purchase_order_count >= 0", name="purchase_order_count_non_negative"),
        CheckConstraint("goods_receipt_count >= 0", name="goods_receipt_count_non_negative"),
        CheckConstraint("supplier_invoice_count >= 0", name="supplier_invoice_count_non_negative"),
    )

    scope_key: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    purchase_order_count: Mapped[int] = mapped_column(Integer, nullable=False)
    goods_receipt_count: Mapped[int] = mapped_column(Integer, nullable=False)
    supplier_invoice_count: Mapped[int] = mapped_column(Integer, nullable=False)
    exception_count: Mapped[int] = mapped_column(Integer, nullable=False)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False)
    warning_count: Mapped[int] = mapped_column(Integer, nullable=False)
    info_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total_financial_impact: Mapped[Decimal] = mapped_column(Money, nullable=False)
    tolerances: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    run_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    exceptions: Mapped[list[ReconciliationException]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"ReconciliationRun(id={self.id!r}, scope_key={self.scope_key!r}, "
            f"version={self.version!r})"
        )


class ReconciliationException(IdMixin, ActiveMixin, TimestampMixin, Base):
    """One quantity, price or identity difference found by a run.

    Source foreign keys keep the PO, receipt and invoice rows that produced
    the difference. ``expected_value`` and ``actual_value`` are formatted
    strings so a quantity, a cost and a currency code can share the columns.
    ``financial_impact`` is signed: over-billing is positive, a short receipt
    is negative. ``resolution_status`` starts ``open`` and can be updated.
    """

    __tablename__ = "reconciliation_exceptions"
    __table_args__ = (
        CheckConstraint(f"severity IN ({_SEVERITIES})", name="severity_known"),
        CheckConstraint(f"resolution_status IN ({_RESOLUTIONS})", name="resolution_known"),
    )

    reconciliation_run_id: Mapped[int] = mapped_column(
        IdType,
        ForeignKey("reconciliation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    purchase_order_id: Mapped[int | None] = mapped_column(
        IdType,
        ForeignKey("purchase_orders.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    purchase_order_line_id: Mapped[int | None] = mapped_column(
        IdType,
        ForeignKey("purchase_order_lines.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    goods_receipt_id: Mapped[int | None] = mapped_column(
        IdType,
        ForeignKey("goods_receipts.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    goods_receipt_line_id: Mapped[int | None] = mapped_column(
        IdType,
        ForeignKey("goods_receipt_lines.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    supplier_invoice_id: Mapped[int | None] = mapped_column(
        IdType,
        ForeignKey("supplier_invoices.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    supplier_invoice_line_id: Mapped[int | None] = mapped_column(
        IdType,
        ForeignKey("supplier_invoice_lines.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    product_id: Mapped[int | None] = mapped_column(
        IdType, ForeignKey("products.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    expected_value: Mapped[str] = mapped_column(String(64), nullable=False)
    actual_value: Mapped[str] = mapped_column(String(64), nullable=False)
    financial_impact: Mapped[Decimal] = mapped_column(Money, nullable=False)
    resolution_status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'open'"), index=True
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)

    run: Mapped[ReconciliationRun] = relationship(back_populates="exceptions")

    def __repr__(self) -> str:
        return f"ReconciliationException(run_id={self.reconciliation_run_id!r}, code={self.code!r})"
