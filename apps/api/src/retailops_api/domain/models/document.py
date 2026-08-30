from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from retailops_api.db.base import ActiveMixin, Base, CreatedAtMixin, IdMixin, IdType, TimestampMixin

if TYPE_CHECKING:
    from retailops_api.domain.models.supplier import Supplier


class DocumentType(StrEnum):
    """Kind of supplier file. Only tabular offer sheets are processed today."""

    supplier_sheet = "supplier_sheet"


class DocumentStatus(StrEnum):
    """How far processing got.

    Happy path: ``received`` → ``parsed`` → ``validated`` → ``review_ready``.
    ``parse_failed`` is terminal when the bytes cannot be turned into rows.
    """

    received = "received"
    parsed = "parsed"
    parse_failed = "parse_failed"
    validated = "validated"
    review_ready = "review_ready"


class FindingSeverity(StrEnum):
    error = "error"
    warning = "warning"
    info = "info"


_DOCUMENT_TYPES = ", ".join(f"'{item.value}'" for item in DocumentType)
_DOCUMENT_STATUSES = ", ".join(f"'{item.value}'" for item in DocumentStatus)
_FINDING_SEVERITIES = ", ".join(f"'{item.value}'" for item in FindingSeverity)


class SupplierDocument(IdMixin, ActiveMixin, TimestampMixin, Base):
    """A supplier file that was stored and, when possible, reviewed.

    The bytes live behind ``storage_key`` on a document store. This row is the
    durable record: who sent it, what it is, the checksum of those bytes, and
    how far processing got. Findings are owned by the document and removed
    with it.
    """

    __tablename__ = "supplier_documents"
    __table_args__ = (
        CheckConstraint(f"document_type IN ({_DOCUMENT_TYPES})", name="document_type_known"),
        CheckConstraint(f"status IN ({_DOCUMENT_STATUSES})", name="status_known"),
    )

    supplier_id: Mapped[int] = mapped_column(
        IdType, ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    media_type: Mapped[str] = mapped_column(String(127), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    document_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    supplier: Mapped[Supplier] = relationship()
    findings: Mapped[list[DocumentFinding]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"SupplierDocument(id={self.id!r}, supplier_id={self.supplier_id!r}, "
            f"status={self.status!r})"
        )


class DocumentFinding(IdMixin, CreatedAtMixin, Base):
    """One deterministic observation about a stored supplier document.

    Findings are not edited. Re-processing a document replaces the set. There
    is no ``updated_at`` or ``active`` flag: a finding is a fact about that
    processing pass.
    """

    __tablename__ = "document_findings"
    __table_args__ = (
        CheckConstraint(f"severity IN ({_FINDING_SEVERITIES})", name="severity_known"),
    )

    document_id: Mapped[int] = mapped_column(
        IdType,
        ForeignKey("supplier_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    field: Mapped[str | None] = mapped_column(String(64), nullable=True)
    row_reference: Mapped[int | None] = mapped_column(Integer, nullable=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_value: Mapped[str | None] = mapped_column(String(200), nullable=True)

    document: Mapped[SupplierDocument] = relationship(back_populates="findings")

    def __repr__(self) -> str:
        return (
            f"DocumentFinding(document_id={self.document_id!r}, "
            f"code={self.code!r}, row_reference={self.row_reference!r})"
        )
