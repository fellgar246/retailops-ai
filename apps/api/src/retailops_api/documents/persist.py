"""Write supplier documents and replace their findings.

None of these helpers commit. The caller owns the transaction.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.orm import Session

from retailops_api.documents.storage import StoredObject
from retailops_api.documents.types import Finding
from retailops_api.domain.models.document import (
    DocumentFinding,
    DocumentStatus,
    DocumentType,
    SupplierDocument,
)


def create_received_document(
    session: Session,
    *,
    supplier_id: int,
    stored: StoredObject,
    document_type: DocumentType = DocumentType.supplier_sheet,
) -> SupplierDocument:
    document = SupplierDocument(
        supplier_id=supplier_id,
        filename=stored.filename,
        media_type=stored.media_type,
        storage_key=stored.key,
        checksum=stored.checksum,
        document_type=document_type.value,
        status=DocumentStatus.received.value,
    )
    session.add(document)
    session.flush()
    return document


def set_status(session: Session, document: SupplierDocument, status: DocumentStatus) -> None:
    document.status = status.value
    session.flush()


def replace_findings(
    session: Session,
    document: SupplierDocument,
    findings: Sequence[Finding],
) -> None:
    document.findings.clear()
    session.flush()
    for item in findings:
        document.findings.append(
            DocumentFinding(
                document_id=document.id,
                code=item.code,
                field=item.field,
                row_reference=item.row_number,
                severity=item.severity.value,
                message=item.message,
                proposed_value=item.proposed_value,
            )
        )
    session.flush()
