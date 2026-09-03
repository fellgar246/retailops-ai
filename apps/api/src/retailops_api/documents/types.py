"""Shared types for supplier-document processing.

The persistence models live in ``retailops_api.domain.models.document``.
These dataclasses are the in-memory shape used by parsers, rules and the
orchestrator before anything is written.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from retailops_api.domain.models.document import FindingSeverity

REQUIRED_SHEET_FIELDS = (
    "supplier_sku",
    "description",
    "category",
    "cost",
    "vat",
    "case_pack",
    "minimum_order_quantity",
    "lead_time_days",
)

DEFAULT_ALLOWED_VAT = (Decimal("0"), Decimal("8"), Decimal("16"))


class DocumentProcessError(ValueError):
    """The submission cannot start: unknown supplier, missing file, empty path."""


class StorageError(ValueError):
    """Illegal key, missing object, or a path that would leave the store root."""


class ParseError(ValueError):
    """The bytes cannot be turned into a supplier sheet.

    ``issues`` is the full list of structural problems (no header, unsupported
    media type, empty payload). Row-level problems that still leave a sheet
    stay on :class:`ParseResult` instead.
    """

    def __init__(self, message: str, issues: list[ParseIssue] | None = None) -> None:
        self.issues = list(issues or [])
        super().__init__(message)


@dataclass(frozen=True)
class ParseIssue:
    """One structural or cell-level problem found while reading a file."""

    code: str
    message: str
    row_number: int = 0
    field: str | None = None


@dataclass(frozen=True)
class Finding:
    """One deterministic observation about a parsed sheet."""

    code: str
    severity: FindingSeverity
    message: str
    field: str | None = None
    row_number: int | None = None
    proposed_value: str | None = None


@dataclass(frozen=True)
class SupplierSheetRow:
    """One normalised offer line, plus the source row number (1-based).

    ``invalid_fields`` names cells that were present but unreadable. Required-
    field rules skip those so a malformed cost is not also reported as missing.
    """

    row_number: int
    supplier_sku: str | None = None
    ean: str | None = None
    description: str | None = None
    category: str | None = None
    cost: Decimal | None = None
    vat: Decimal | None = None
    case_pack: int | None = None
    minimum_order_quantity: int | None = None
    lead_time_days: int | None = None
    invalid_fields: frozenset[str] = field(default_factory=frozenset)
    page: int | None = None
    confidence: float | None = None


@dataclass(frozen=True)
class ExtractionMeta:
    """Provenance for a parse. Missing numbers stay ``None``; nothing is invented."""

    analyzer: str = "local"
    page_count: int | None = None
    table_count: int = 0
    line_count: int = 0
    form_count: int = 0
    min_confidence: float | None = None
    max_confidence: float | None = None
    ambiguous: bool = False


@dataclass(frozen=True)
class ParseResult:
    rows: tuple[SupplierSheetRow, ...]
    issues: tuple[ParseIssue, ...] = ()
    extraction: ExtractionMeta | None = None


@dataclass(frozen=True)
class RuleConfig:
    """Tunable constants for the deterministic sheet rules."""

    allowed_vat: tuple[Decimal, ...] = DEFAULT_ALLOWED_VAT
    required_fields: tuple[str, ...] = REQUIRED_SHEET_FIELDS


@dataclass(frozen=True)
class ProcessResult:
    """Outcome of one intake pass. The caller owns the transaction."""

    document_id: int
    supplier_code: str
    filename: str
    storage_key: str
    checksum: str
    status: str
    row_count: int
    findings: tuple[Finding, ...]
