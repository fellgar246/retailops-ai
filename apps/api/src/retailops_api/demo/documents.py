"""Store and validate the demo supplier sheets."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from retailops_api.demo.sheets import DEMO_SHEETS, DemoSheet
from retailops_api.documents.process import process_document
from retailops_api.documents.storage import LocalDocumentStorage
from retailops_api.documents.types import ProcessResult
from retailops_api.domain.models import SupplierDocument
from retailops_api.domain.repositories import get_supplier_by_code


def ingest_demo_documents(
    session: Session,
    storage_root: Path,
) -> list[ProcessResult]:
    """Process each demo sheet once. A filename already stored is skipped."""

    storage = LocalDocumentStorage(storage_root)
    results: list[ProcessResult] = []
    for sheet in DEMO_SHEETS:
        existing = _existing_document(session, sheet)
        if existing is not None:
            results.append(
                ProcessResult(
                    document_id=existing.id,
                    supplier_code=sheet.supplier_code,
                    filename=existing.filename,
                    storage_key=existing.storage_key,
                    checksum=existing.checksum,
                    status=existing.status,
                    row_count=0,
                    findings=(),
                )
            )
            continue
        results.append(
            process_document(
                session,
                storage,
                supplier_code=sheet.supplier_code,
                filename=sheet.filename,
                data=sheet.body.encode("utf-8"),
            )
        )
    session.flush()
    return results


def _existing_document(session: Session, sheet: DemoSheet) -> SupplierDocument | None:
    supplier = get_supplier_by_code(session, sheet.supplier_code)
    if supplier is None:
        return None
    return session.scalar(
        select(SupplierDocument).where(
            SupplierDocument.supplier_id == supplier.id,
            SupplierDocument.filename == sheet.filename,
        )
    )
