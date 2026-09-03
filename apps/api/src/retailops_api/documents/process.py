"""Coordinate intake, storage, parse, validation and finding persistence.

    intake → storage → parse → normalise → validate → persist findings → status

Statuses are written as the work happens so a failed parse is distinct from a
sheet that was reviewed. The caller owns the transaction.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from retailops_api.core.limits import DocumentBounds
from retailops_api.documents.catalog import load_catalog_index
from retailops_api.documents.catalog_rules import validate_against_catalog
from retailops_api.documents.parse import SheetAnalyzer, detect_media_type, parse_supplier_sheet
from retailops_api.documents.persist import create_received_document, replace_findings, set_status
from retailops_api.documents.rules import validate_sheet
from retailops_api.documents.storage import DocumentStorage
from retailops_api.documents.types import (
    DocumentProcessError,
    Finding,
    ParseError,
    ParseIssue,
    ProcessResult,
    RuleConfig,
)
from retailops_api.domain.models.document import (
    DocumentStatus,
    DocumentType,
    FindingSeverity,
    SupplierDocument,
)
from retailops_api.domain.repositories import get_supplier_by_code


def process_document(
    session: Session,
    storage: DocumentStorage,
    *,
    supplier_code: str,
    filename: str,
    data: bytes,
    media_type: str | None = None,
    document_type: DocumentType = DocumentType.supplier_sheet,
    rule_config: RuleConfig | None = None,
    analyzer: SheetAnalyzer | None = None,
    bounds: DocumentBounds | None = None,
) -> ProcessResult:
    supplier = get_supplier_by_code(session, supplier_code)
    if supplier is None:
        raise DocumentProcessError(f"unknown supplier {supplier_code!r}")

    limits = bounds or DocumentBounds()
    if len(data) > limits.max_upload_bytes:
        raise DocumentProcessError(
            f"document exceeds max upload size ({limits.max_upload_bytes} bytes)"
        )

    detected = _safe_media_type(filename, media_type)
    stored = storage.save(data, filename=filename, media_type=detected)
    document = create_received_document(
        session,
        supplier_id=supplier.id,
        stored=stored,
        document_type=document_type,
    )

    try:
        parsed = parse_supplier_sheet(
            data,
            media_type=detected,
            filename=stored.filename,
            analyzer=analyzer,
            bounds=limits,
        )
    except ParseError as error:
        findings = [_issue_to_finding(issue) for issue in error.issues] or [
            Finding(
                code="parse_failed",
                severity=FindingSeverity.error,
                message=str(error),
            )
        ]
        replace_findings(session, document, findings)
        set_status(session, document, DocumentStatus.parse_failed)
        return _result(document, supplier_code, stored.filename, row_count=0, findings=findings)

    set_status(session, document, DocumentStatus.parsed)

    config = rule_config or RuleConfig()
    findings = [_issue_to_finding(issue) for issue in parsed.issues]
    findings.extend(validate_sheet(parsed.rows, config=config))
    findings.extend(
        validate_against_catalog(parsed.rows, load_catalog_index(session), supplier_id=supplier.id)
    )
    findings = _sorted_findings(findings)

    replace_findings(session, document, findings)
    set_status(session, document, DocumentStatus.validated)
    set_status(session, document, DocumentStatus.review_ready)
    return _result(
        document,
        supplier_code,
        stored.filename,
        row_count=len(parsed.rows),
        findings=findings,
    )


def _safe_media_type(filename: str, media_type: str | None) -> str:
    try:
        return detect_media_type(filename, media_type)
    except ParseError:
        return media_type or "application/octet-stream"


def _issue_to_finding(issue: ParseIssue) -> Finding:
    return Finding(
        code=issue.code,
        severity=FindingSeverity.error,
        message=issue.message,
        field=issue.field,
        row_number=issue.row_number or None,
    )


def _sorted_findings(findings: list[Finding]) -> list[Finding]:
    return sorted(
        findings,
        key=lambda item: (item.row_number or 0, item.code, item.field or "", item.message),
    )


def _result(
    document: SupplierDocument,
    supplier_code: str,
    filename: str,
    *,
    row_count: int,
    findings: list[Finding],
) -> ProcessResult:
    return ProcessResult(
        document_id=document.id,
        supplier_code=supplier_code,
        filename=filename,
        storage_key=document.storage_key,
        checksum=document.checksum,
        status=document.status,
        row_count=row_count,
        findings=tuple(findings),
    )
