"""Starting work, and following it.

Intake answers before the work runs: Textract and Bedrock take far longer than
a request may stay open. Every start returns a job, and the job is the only
thing the console has to poll.
"""

from __future__ import annotations

import hashlib
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from retailops_api.api.deps import (
    CurrentPrincipal,
    ReviewerPrincipal,
    get_app_settings,
    get_db,
)
from retailops_api.api.paging import DEFAULT_LIMIT, validate_page
from retailops_api.core.adapters import document_storage_for, job_queue_for
from retailops_api.core.config import Settings
from retailops_api.documents.parse import SUPPORTED_MEDIA_TYPES, detect_media_type
from retailops_api.documents.types import ParseError, StorageError
from retailops_api.domain.models.job import JobKind, JobState
from retailops_api.domain.repositories import get_supplier_by_code
from retailops_api.identity.types import Principal
from retailops_api.jobs import store
from retailops_api.jobs.query import list_jobs
from retailops_api.jobs.types import (
    JobConfigError,
    JobNotFoundError,
    JobRequest,
    JobValidationError,
)

router = APIRouter(tags=["jobs"])
DbSession = Annotated[Session, Depends(get_db)]
#: The configuration this application was built with, so an injected one governs.
AppSettings = Annotated[Settings, Depends(get_app_settings)]


class ReconciliationRequest(BaseModel):
    supplier: str = Field(min_length=1, max_length=64)
    invoice: str | None = None
    po: str | None = None
    idempotency_key: str | None = None


class ForecastRequest(BaseModel):
    horizon: int = Field(default=4, ge=1, le=26)
    min_train_periods: int = Field(default=12, ge=1, le=260)
    idempotency_key: str | None = None


@router.post("/documents", status_code=202)
async def upload_document(
    session: DbSession,
    actor: ReviewerPrincipal,
    settings: AppSettings,
    supplier: Annotated[str, Form(min_length=1, max_length=64)],
    file: Annotated[UploadFile, File()],
    idempotency_key: Annotated[str | None, Form()] = None,
) -> dict[str, Any]:
    _require_supplier(session, supplier)

    filename = (file.filename or "").strip()
    if not filename:
        raise HTTPException(status_code=400, detail="the upload has no filename")

    media_type = _supported_media_type(filename)
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="the upload is empty")
    ceiling = settings.aws_config().document_bounds().max_upload_bytes
    if len(data) > ceiling:
        raise HTTPException(
            status_code=413, detail=f"document exceeds max upload size ({ceiling} bytes)"
        )

    # Store first, so the queue carries an identifier rather than a document.
    try:
        stored = document_storage_for(settings).save(data, filename=filename, media_type=media_type)
    except StorageError as error:
        raise HTTPException(
            status_code=502, detail="the document store rejected the file"
        ) from error

    key = idempotency_key or _checksum_key(supplier, stored.checksum)
    return _enqueue(
        session,
        settings,
        actor,
        JobRequest(
            kind=JobKind.document_intake,
            idempotency_key=key,
            request={
                "supplier_code": supplier,
                "storage_key": stored.key,
                "filename": stored.filename,
                "media_type": stored.media_type,
            },
            requested_by=actor.display_name,
            requested_by_subject=actor.audit_subject,
        ),
    )


@router.post("/reconciliations", status_code=202)
def start_reconciliation(
    body: ReconciliationRequest,
    session: DbSession,
    settings: AppSettings,
    actor: ReviewerPrincipal,
) -> dict[str, Any]:
    _require_supplier(session, body.supplier)
    invoice = (body.invoice or "").strip() or None
    po = (body.po or "").strip() or None
    if not invoice and not po:
        raise HTTPException(
            status_code=400, detail="provide a purchase order number or an invoice number"
        )

    key = body.idempotency_key or f"{body.supplier}:{po or ''}:{invoice or ''}"
    return _enqueue(
        session,
        settings,
        actor,
        JobRequest(
            kind=JobKind.reconciliation,
            idempotency_key=key,
            request={
                "supplier_code": body.supplier,
                "invoice_number": invoice,
                "po_number": po,
            },
            requested_by=actor.display_name,
            requested_by_subject=actor.audit_subject,
        ),
    )


@router.post("/forecasts", status_code=202)
def start_forecast(
    body: ForecastRequest,
    session: DbSession,
    settings: AppSettings,
    actor: ReviewerPrincipal,
) -> dict[str, Any]:
    key = body.idempotency_key or f"h{body.horizon}:m{body.min_train_periods}"
    return _enqueue(
        session,
        settings,
        actor,
        JobRequest(
            kind=JobKind.forecast,
            idempotency_key=key,
            request={
                "horizon": body.horizon,
                "min_train_periods": body.min_train_periods,
            },
            requested_by=actor.display_name,
            requested_by_subject=actor.audit_subject,
        ),
    )


@router.get("/jobs")
def job_queue(
    session: DbSession,
    principal: CurrentPrincipal,
    kind: Annotated[list[JobKind] | None, Query()] = None,
    state: Annotated[list[JobState] | None, Query()] = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> dict[str, Any]:
    del principal
    limit, offset = validate_page(limit, offset)
    return list_jobs(
        session,
        limit=limit,
        offset=offset,
        kinds=tuple(kind or ()),
        states=tuple(state or ()),
    )


@router.get("/jobs/{job_id}")
def job_detail(job_id: int, session: DbSession, principal: CurrentPrincipal) -> dict[str, Any]:
    del principal
    try:
        return store.job_view(store.get_job(session, job_id)).to_dict()
    except JobNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


def _enqueue(
    session: Session, settings: Settings, actor: Principal, request: JobRequest
) -> dict[str, Any]:
    del actor
    try:
        job = job_queue_for(settings, session).enqueue(request)
    except JobValidationError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except JobConfigError as error:
        raise HTTPException(status_code=500, detail="the job queue is not configured") from error
    return store.job_view(job).to_dict()


def _require_supplier(session: Session, code: str) -> None:
    if get_supplier_by_code(session, code) is None:
        raise HTTPException(status_code=404, detail=f"supplier {code} not found")


def _supported_media_type(filename: str) -> str:
    """Decide from the filename, not from what the client declared.

    A caller can put any value in the content type header, so trusting it would
    let an unsupported file past the boundary and fail deeper in, after it had
    already been stored.
    """

    try:
        media_type = detect_media_type(filename)
    except ParseError as error:
        raise HTTPException(status_code=415, detail=str(error)) from error
    if media_type not in SUPPORTED_MEDIA_TYPES:
        raise HTTPException(status_code=415, detail=f"unsupported media type {media_type}")
    return media_type


def _checksum_key(supplier: str, checksum: str) -> str:
    """Default key: the same bytes from the same supplier are the same request."""

    return hashlib.sha256(f"{supplier}:{checksum}".encode()).hexdigest()
