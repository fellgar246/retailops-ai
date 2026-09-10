"""What each kind of job actually does.

Every handler calls the same function the command line calls. Moving execution
behind a queue must not change deterministic validation, reconciliation
calculations, routing policy or the audit model.

A handler raises ``PermanentJobError`` when retrying cannot help — an unknown
supplier, an unsupported file — and lets anything else propagate so the worker
can decide whether an attempt remains.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from retailops_api.core.adapters import document_analyzer_for, document_storage_for
from retailops_api.core.config import Settings
from retailops_api.documents.types import DocumentProcessError
from retailops_api.domain.models.job import JobKind, ProcessingJob
from retailops_api.jobs.types import PermanentJobError
from retailops_api.procurement.orchestrate import reconcile
from retailops_api.procurement.types import (
    ReconciliationError,
    ReconciliationScope,
    ReconciliationTolerances,
)

#: A handler receives the job and returns what it produced.
JobHandler = Callable[[Session, Settings, ProcessingJob], dict[str, Any]]


def run_document_intake(session: Session, settings: Settings, job: ProcessingJob) -> dict[str, Any]:
    """Store-backed intake: the bytes were saved before the job was created."""

    from retailops_api.documents.process import process_stored_document

    storage = document_storage_for(settings)
    analyzer = document_analyzer_for(settings)
    request = job.request
    try:
        result = process_stored_document(
            session,
            storage,
            supplier_code=str(request["supplier_code"]),
            storage_key=str(request["storage_key"]),
            filename=str(request["filename"]),
            media_type=request.get("media_type"),
            analyzer=analyzer,
            bounds=settings.aws_config().document_bounds(),
        )
    except DocumentProcessError as error:
        raise PermanentJobError(str(error)) from error
    return {
        "document_id": result.document_id,
        "status": result.status,
        "row_count": result.row_count,
        "finding_count": len(result.findings),
    }


def run_reconciliation(session: Session, settings: Settings, job: ProcessingJob) -> dict[str, Any]:
    del settings
    request = job.request
    try:
        scope = ReconciliationScope(
            supplier_code=str(request["supplier_code"]),
            po_number=_optional(request.get("po_number")),
            invoice_number=_optional(request.get("invoice_number")),
        )
        tolerances = _tolerances(request.get("tolerances"))
        result = reconcile(session, scope, tolerances=tolerances)
    except ReconciliationError as error:
        raise PermanentJobError(str(error)) from error
    return {
        "reconciliation_run_id": result.run_id,
        "scope_key": result.scope_key,
        "version": result.version,
        "reused": result.reused,
        "exception_count": result.exception_count,
    }


def run_forecast(session: Session, settings: Settings, job: ProcessingJob) -> dict[str, Any]:
    del settings
    from retailops_api.forecasting.evaluate_run import evaluate_from_database

    request = job.request
    try:
        run = evaluate_from_database(
            session,
            horizon=int(request["horizon"]),
            min_train_periods=int(request["min_train_periods"]),
        )
    except ValueError as error:
        raise PermanentJobError(str(error)) from error
    return {
        "forecast_run_id": run.run_id,
        "model_id": run.model_id,
        "prediction_count": run.prediction_count,
        "complete_weeks": run.complete_weeks,
    }


HANDLERS: dict[JobKind, JobHandler] = {
    JobKind.document_intake: run_document_intake,
    JobKind.reconciliation: run_reconciliation,
    JobKind.forecast: run_forecast,
}


def handler_for(kind: JobKind) -> JobHandler:
    handler = HANDLERS.get(kind)
    if handler is None:  # pragma: no cover - every kind is registered
        raise PermanentJobError(f"no handler for {kind.value}")
    return handler


def _optional(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _tolerances(raw: object) -> ReconciliationTolerances | None:
    if not isinstance(raw, dict):
        return None
    return ReconciliationTolerances(
        quantity_tolerance=int(raw["quantity_tolerance"]),
        monetary_tolerance=Decimal(str(raw["monetary_tolerance"])),
        price_percent_tolerance=Decimal(str(raw["price_percent_tolerance"])),
    )
