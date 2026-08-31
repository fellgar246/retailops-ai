"""Read supplier documents for the operations API. Does not commit."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from retailops_api.documents.parse import parse_supplier_sheet
from retailops_api.documents.storage import DocumentStorage
from retailops_api.documents.types import ParseError, StorageError, SupplierSheetRow
from retailops_api.domain.models import DocumentFinding, ReviewCase, Supplier, SupplierDocument
from retailops_api.review.persist import case_view


def list_documents(
    session: Session,
    *,
    limit: int,
    offset: int,
    status: Sequence[str] = (),
    supplier: str | None = None,
    supplier_id: int | None = None,
) -> dict[str, Any]:
    stmt = _apply_filters(
        select(SupplierDocument), status=status, supplier=supplier, supplier_id=supplier_id
    )
    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    documents = session.scalars(
        stmt.options(selectinload(SupplierDocument.supplier))
        .order_by(SupplierDocument.updated_at.desc(), SupplierDocument.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    summaries = _severity_summaries(session, [item.id for item in documents])
    return {
        "items": [
            document_summary(item, severity=summaries.get(item.id, _empty_severity()))
            for item in documents
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def get_document(
    session: Session,
    document_id: int,
    storage: DocumentStorage | None = None,
) -> dict[str, Any] | None:
    document = session.get(
        SupplierDocument,
        document_id,
        options=(
            selectinload(SupplierDocument.supplier),
            selectinload(SupplierDocument.findings),
        ),
    )
    if document is None:
        return None
    return document_detail(session, document, storage)


def document_summary(
    document: SupplierDocument, *, severity: dict[str, int] | None = None
) -> dict[str, Any]:
    counts = severity or _empty_severity()
    supplier = document.supplier
    return {
        "id": document.id,
        "supplier_id": document.supplier_id,
        "supplier_code": None if supplier is None else supplier.code,
        "supplier_name": None if supplier is None else supplier.name,
        "filename": document.filename,
        "media_type": document.media_type,
        "status": document.status,
        "finding_count": counts["error"] + counts["warning"] + counts["info"],
        "severity_summary": counts,
        "processed_at": document.updated_at.isoformat(),
        "created_at": document.created_at.isoformat(),
    }


def document_detail(
    session: Session,
    document: SupplierDocument,
    storage: DocumentStorage | None,
) -> dict[str, Any]:
    findings = sorted(
        document.findings,
        key=lambda item: (item.row_reference or 0, item.code, item.field or "", item.id),
    )
    severity = _empty_severity()
    for item in findings:
        if item.severity in severity:
            severity[item.severity] += 1
    payload = document_summary(document, severity=severity)
    payload["checksum"] = document.checksum
    payload["storage_key"] = document.storage_key
    payload["document_type"] = document.document_type
    payload["findings"] = [finding_dict(item) for item in findings]
    payload["review_cases"] = _related_cases(session, [item.id for item in findings])
    rows, available = _normalized_rows(document, storage)
    payload["rows"] = rows
    payload["rows_available"] = available
    return payload


def finding_dict(finding: DocumentFinding) -> dict[str, Any]:
    return {
        "id": finding.id,
        "code": finding.code,
        "field": finding.field,
        "row_reference": finding.row_reference,
        "severity": finding.severity,
        "message": finding.message,
        "proposed_value": finding.proposed_value,
        "created_at": finding.created_at.isoformat(),
        "provenance": "rule",
    }


def _apply_filters(
    stmt: Select[tuple[SupplierDocument]],
    *,
    status: Sequence[str],
    supplier: str | None,
    supplier_id: int | None,
) -> Select[tuple[SupplierDocument]]:
    if status:
        stmt = stmt.where(SupplierDocument.status.in_(list(status)))
    if supplier_id is not None:
        stmt = stmt.where(SupplierDocument.supplier_id == supplier_id)
    elif supplier is not None:
        stmt = stmt.join(Supplier).where(Supplier.code == supplier)
    return stmt


def _severity_summaries(session: Session, document_ids: Sequence[int]) -> dict[int, dict[str, int]]:
    if not document_ids:
        return {}
    rows = session.execute(
        select(DocumentFinding.document_id, DocumentFinding.severity, func.count())
        .where(DocumentFinding.document_id.in_(document_ids))
        .group_by(DocumentFinding.document_id, DocumentFinding.severity)
    ).all()
    summaries: dict[int, dict[str, int]] = defaultdict(_empty_severity)
    for document_id, severity, count in rows:
        if severity in summaries[int(document_id)]:
            summaries[int(document_id)][str(severity)] = int(count)
    return dict(summaries)


def _empty_severity() -> dict[str, int]:
    return {"error": 0, "warning": 0, "info": 0}


def _related_cases(session: Session, finding_ids: Sequence[int]) -> list[dict[str, Any]]:
    if not finding_ids:
        return []
    cases = session.scalars(
        select(ReviewCase)
        .where(ReviewCase.document_finding_id.in_(finding_ids))
        .order_by(ReviewCase.id.asc())
    ).all()
    return [case_view(item).to_dict() for item in cases]


def _normalized_rows(
    document: SupplierDocument, storage: DocumentStorage | None
) -> tuple[list[dict[str, Any]], bool]:
    if storage is None:
        return [], False
    try:
        data = storage.read(document.storage_key)
        parsed = parse_supplier_sheet(
            data, media_type=document.media_type, filename=document.filename
        )
    except (StorageError, ParseError, OSError, ValueError):
        return [], False
    return [_row_dict(row) for row in parsed.rows], True


def _row_dict(row: SupplierSheetRow) -> dict[str, Any]:
    return {
        "row_number": row.row_number,
        "supplier_sku": row.supplier_sku,
        "ean": row.ean,
        "description": row.description,
        "category": row.category,
        "cost": None if row.cost is None else str(row.cost),
        "vat": None if row.vat is None else str(row.vat),
        "case_pack": row.case_pack,
        "minimum_order_quantity": row.minimum_order_quantity,
        "lead_time_days": row.lead_time_days,
        "invalid_fields": sorted(row.invalid_fields),
        "provenance": "extracted",
    }
