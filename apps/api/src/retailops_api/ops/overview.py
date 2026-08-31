"""Assemble the operations overview from persisted forecast, document and review facts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from retailops_api.core.config import get_settings
from retailops_api.domain.models import (
    ForecastRun,
    ReconciliationException,
    ReconciliationRun,
    ReviewCase,
    SupplierDocument,
)
from retailops_api.domain.models.document import DocumentStatus
from retailops_api.domain.models.reconciliation import ExceptionResolution, ExceptionSeverity
from retailops_api.domain.models.review import ReviewStatus
from retailops_api.forecasting.query import run_summary
from retailops_api.review.metrics import collect_metrics


def collect_overview(session: Session) -> dict[str, Any]:
    latest = session.scalar(select(ForecastRun).order_by(ForecastRun.generated_at.desc()).limit(1))
    forecast_count = session.scalar(select(func.count()).select_from(ForecastRun)) or 0
    document_total = session.scalar(select(func.count()).select_from(SupplierDocument)) or 0
    awaiting = (
        session.scalar(
            select(func.count()).where(SupplierDocument.status == DocumentStatus.review_ready.value)
        )
        or 0
    )
    parse_failed = (
        session.scalar(
            select(func.count()).where(SupplierDocument.status == DocumentStatus.parse_failed.value)
        )
        or 0
    )
    open_exceptions = (
        session.scalar(
            select(func.count()).where(
                ReconciliationException.resolution_status == ExceptionResolution.open.value
            )
        )
        or 0
    )
    error_exceptions = (
        session.scalar(
            select(func.count()).where(
                ReconciliationException.resolution_status == ExceptionResolution.open.value,
                ReconciliationException.severity == ExceptionSeverity.error.value,
            )
        )
        or 0
    )
    impact = session.scalar(
        select(func.coalesce(func.sum(ReconciliationException.financial_impact), 0)).where(
            ReconciliationException.resolution_status == ExceptionResolution.open.value
        )
    )
    run_count = session.scalar(select(func.count()).select_from(ReconciliationRun)) or 0
    in_review = (
        session.scalar(
            select(func.count()).where(ReviewCase.status == ReviewStatus.in_review.value)
        )
        or 0
    )
    metrics = collect_metrics(session)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "environment": get_settings().environment,
        "forecasts": {
            "run_count": forecast_count,
            "latest": None if latest is None else run_summary(latest),
        },
        "documents": {
            "total": document_total,
            "awaiting_review": awaiting,
            "parse_failed": parse_failed,
        },
        "reconciliation": {
            "run_count": run_count,
            "open_exceptions": open_exceptions,
            "error_exceptions": error_exceptions,
            "total_financial_impact": str(impact),
        },
        "reviews": {
            **metrics.to_dict(),
            "in_review": in_review,
        },
    }
