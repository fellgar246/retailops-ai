"""Cross-entity search for the operations shell. Does not commit."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from retailops_api.domain.models import (
    ForecastRun,
    GoodsReceipt,
    PurchaseOrder,
    ReconciliationException,
    ReviewCase,
    Supplier,
    SupplierDocument,
    SupplierInvoice,
)

_LIMIT = 8


def search_operations(session: Session, query: str) -> dict[str, Any]:
    text = query.strip()
    if not text:
        return {"query": text, "documents": [], "reviews": [], "exceptions": [], "forecasts": []}
    like = f"%{text.lower()}%"
    numeric = _as_int(text)
    documents = session.scalars(
        select(SupplierDocument)
        .join(Supplier)
        .options(selectinload(SupplierDocument.supplier))
        .where(
            or_(
                func.lower(SupplierDocument.filename).like(like),
                func.lower(Supplier.code).like(like),
            )
        )
        .order_by(SupplierDocument.id.desc())
        .limit(_LIMIT)
    ).all()
    reviews = session.scalars(
        _review_stmt(numeric, like).order_by(ReviewCase.id.desc()).limit(_LIMIT)
    ).all()
    exceptions = session.scalars(
        select(ReconciliationException)
        .outerjoin(PurchaseOrder, ReconciliationException.purchase_order_id == PurchaseOrder.id)
        .outerjoin(
            SupplierInvoice, ReconciliationException.supplier_invoice_id == SupplierInvoice.id
        )
        .outerjoin(GoodsReceipt, ReconciliationException.goods_receipt_id == GoodsReceipt.id)
        .where(
            or_(
                func.lower(ReconciliationException.code).like(like),
                func.lower(ReconciliationException.message).like(like),
                func.lower(PurchaseOrder.po_number).like(like),
                func.lower(SupplierInvoice.invoice_number).like(like),
                func.lower(GoodsReceipt.receipt_number).like(like),
            )
        )
        .order_by(ReconciliationException.id.desc())
        .limit(_LIMIT)
    ).all()
    forecasts = session.scalars(
        select(ForecastRun)
        .where(
            or_(
                func.lower(ForecastRun.model_id).like(like),
                func.lower(ForecastRun.problem_id).like(like),
            )
        )
        .order_by(ForecastRun.id.desc())
        .limit(_LIMIT)
    ).all()
    return {
        "query": text,
        "documents": [
            {
                "id": item.id,
                "filename": item.filename,
                "supplier_code": None if item.supplier is None else item.supplier.code,
                "status": item.status,
            }
            for item in documents
        ],
        "reviews": [
            {
                "id": item.id,
                "status": item.status,
                "subject_type": item.subject_type,
                "priority": item.priority,
            }
            for item in reviews
        ],
        "exceptions": [
            {
                "id": item.id,
                "code": item.code,
                "severity": item.severity,
                "reconciliation_run_id": item.reconciliation_run_id,
            }
            for item in exceptions
        ],
        "forecasts": [
            {
                "id": item.id,
                "model_id": item.model_id,
                "cutoff": item.cutoff.isoformat(),
            }
            for item in forecasts
        ],
    }


def _review_stmt(numeric: int | None, like: str) -> Any:
    stmt = select(ReviewCase).outerjoin(Supplier, ReviewCase.supplier_id == Supplier.id)
    clauses: list[Any] = [
        func.lower(Supplier.code).like(like),
        func.lower(ReviewCase.reviewer).like(like),
    ]
    if numeric is not None:
        clauses.append(ReviewCase.id == numeric)
    return stmt.where(or_(*clauses))


def _as_int(value: str) -> int | None:
    try:
        return int(value)
    except ValueError:
        return None
