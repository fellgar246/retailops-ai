from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from retailops_api.api.deps import get_db
from retailops_api.api.paging import DEFAULT_LIMIT, validate_page
from retailops_api.core.config import get_settings
from retailops_api.documents.paths import default_document_root
from retailops_api.documents.query import get_document, list_documents
from retailops_api.documents.storage import LocalDocumentStorage
from retailops_api.domain.repositories import get_supplier_by_code

router = APIRouter(prefix="/documents", tags=["documents"])
DbSession = Annotated[Session, Depends(get_db)]


def get_document_storage() -> LocalDocumentStorage:
    settings = get_settings()
    root = (
        Path(settings.document_storage_root)
        if settings.document_storage_root
        else default_document_root()
    )
    return LocalDocumentStorage(root)


@router.get("")
def supplier_documents(
    session: DbSession,
    status: Annotated[list[str] | None, Query()] = None,
    supplier: str | None = None,
    supplier_id: int | None = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> dict[str, Any]:
    limit, offset = validate_page(limit, offset)
    resolved_supplier = supplier_id
    if supplier is not None:
        row = get_supplier_by_code(session, supplier)
        if row is None:
            raise HTTPException(status_code=404, detail=f"supplier {supplier} not found")
        resolved_supplier = row.id
    return list_documents(
        session,
        limit=limit,
        offset=offset,
        status=tuple(status or ()),
        supplier_id=resolved_supplier,
    )


@router.get("/{document_id}")
def supplier_document(
    document_id: int,
    session: DbSession,
    storage: Annotated[LocalDocumentStorage, Depends(get_document_storage)],
) -> dict[str, Any]:
    payload = get_document(session, document_id, storage)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"document {document_id} not found")
    return payload
