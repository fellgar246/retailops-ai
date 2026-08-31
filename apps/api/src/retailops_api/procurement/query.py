"""Read reconciliation runs and exceptions for the operations API. Does not commit."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from retailops_api.domain.models import (
    GoodsReceipt,
    Product,
    PurchaseOrder,
    ReconciliationException,
    ReconciliationRun,
    ReviewCase,
    SupplierInvoice,
)
from retailops_api.domain.models.reconciliation import ExceptionResolution
from retailops_api.review.persist import case_view


def list_runs(session: Session, *, limit: int, offset: int) -> dict[str, Any]:
    total = session.scalar(select(func.count()).select_from(ReconciliationRun)) or 0
    runs = session.scalars(
        select(ReconciliationRun)
        .order_by(ReconciliationRun.generated_at.desc(), ReconciliationRun.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    open_counts = _open_exception_counts(session, [run.id for run in runs])
    return {
        "items": [
            run_summary(run, open_exception_count=open_counts.get(run.id, 0)) for run in runs
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def get_run(session: Session, run_id: int) -> dict[str, Any] | None:
    run = session.get(
        ReconciliationRun,
        run_id,
        options=(selectinload(ReconciliationRun.exceptions),),
    )
    if run is None:
        return None
    return run_detail(session, run)


def list_exceptions(
    session: Session,
    *,
    limit: int,
    offset: int,
    severity: Sequence[str] = (),
    resolution: Sequence[str] = (),
    code: str | None = None,
) -> dict[str, Any]:
    stmt = _exception_filters(
        select(ReconciliationException),
        severity=severity,
        resolution=resolution,
        code=code,
    )
    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = session.scalars(
        stmt.order_by(
            ReconciliationException.severity.asc(),
            ReconciliationException.id.asc(),
        )
        .limit(limit)
        .offset(offset)
    ).all()
    return {
        "items": exception_payloads(session, rows),
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def run_summary(
    run: ReconciliationRun, *, open_exception_count: int | None = None
) -> dict[str, Any]:
    open_count = open_exception_count
    if open_count is None:
        open_count = sum(
            1 for item in run.exceptions if item.resolution_status == ExceptionResolution.open.value
        )
    return {
        "id": run.id,
        "scope_key": run.scope_key,
        "version": run.version,
        "generated_at": run.generated_at.isoformat(),
        "purchase_order_count": run.purchase_order_count,
        "goods_receipt_count": run.goods_receipt_count,
        "supplier_invoice_count": run.supplier_invoice_count,
        "exception_count": run.exception_count,
        "error_count": run.error_count,
        "warning_count": run.warning_count,
        "info_count": run.info_count,
        "open_exception_count": open_count,
        "total_financial_impact": str(run.total_financial_impact),
        "created_at": run.created_at.isoformat(),
    }


def run_detail(session: Session, run: ReconciliationRun) -> dict[str, Any]:
    payload = run_summary(run)
    payload["tolerances"] = run.tolerances
    payload["input_fingerprint"] = run.input_fingerprint
    payload["exceptions"] = exception_payloads(session, run.exceptions)
    return payload


def exception_payloads(
    session: Session, exceptions: Sequence[ReconciliationException]
) -> list[dict[str, Any]]:
    context = _load_context(session, exceptions)
    return [exception_dict(item, context) for item in exceptions]


def exception_dict(
    exception: ReconciliationException, context: dict[str, Any] | None = None
) -> dict[str, Any]:
    bag = context or {}
    purchase_order = bag.get("purchase_orders", {}).get(exception.purchase_order_id)
    receipt = bag.get("receipts", {}).get(exception.goods_receipt_id)
    invoice = bag.get("invoices", {}).get(exception.supplier_invoice_id)
    product = bag.get("products", {}).get(exception.product_id)
    review = bag.get("reviews", {}).get(exception.id)
    return {
        "id": exception.id,
        "reconciliation_run_id": exception.reconciliation_run_id,
        "code": exception.code,
        "severity": exception.severity,
        "expected_value": exception.expected_value,
        "actual_value": exception.actual_value,
        "financial_impact": str(exception.financial_impact),
        "resolution_status": exception.resolution_status,
        "message": exception.message,
        "purchase_order": _ref(purchase_order, "po_number") if purchase_order is not None else None,
        "goods_receipt": _ref(receipt, "receipt_number") if receipt is not None else None,
        "supplier_invoice": _ref(invoice, "invoice_number") if invoice is not None else None,
        "product": None
        if product is None
        else {"id": product.id, "sku": product.sku, "name": product.name},
        "review_case_id": None if review is None else review.id,
        "review_status": None if review is None else review.status,
        "provenance": "rule",
        "created_at": exception.created_at.isoformat(),
    }


def _exception_filters(
    stmt: Select[tuple[ReconciliationException]],
    *,
    severity: Sequence[str],
    resolution: Sequence[str],
    code: str | None,
) -> Select[tuple[ReconciliationException]]:
    if severity:
        stmt = stmt.where(ReconciliationException.severity.in_(list(severity)))
    if resolution:
        stmt = stmt.where(ReconciliationException.resolution_status.in_(list(resolution)))
    if code is not None:
        stmt = stmt.where(ReconciliationException.code == code)
    return stmt


def _open_exception_counts(session: Session, run_ids: Sequence[int]) -> dict[int, int]:
    if not run_ids:
        return {}
    rows = session.execute(
        select(ReconciliationException.reconciliation_run_id, func.count())
        .where(
            ReconciliationException.reconciliation_run_id.in_(run_ids),
            ReconciliationException.resolution_status == ExceptionResolution.open.value,
        )
        .group_by(ReconciliationException.reconciliation_run_id)
    ).all()
    return {int(run_id): int(count) for run_id, count in rows}


def _load_context(
    session: Session, exceptions: Sequence[ReconciliationException]
) -> dict[str, Any]:
    po_ids = {item.purchase_order_id for item in exceptions if item.purchase_order_id is not None}
    receipt_ids = {
        item.goods_receipt_id for item in exceptions if item.goods_receipt_id is not None
    }
    invoice_ids = {
        item.supplier_invoice_id for item in exceptions if item.supplier_invoice_id is not None
    }
    product_ids = {item.product_id for item in exceptions if item.product_id is not None}
    exception_ids = [item.id for item in exceptions]
    reviews = session.scalars(
        select(ReviewCase).where(ReviewCase.reconciliation_exception_id.in_(exception_ids or [0]))
    ).all()
    return {
        "purchase_orders": _by_id(session, PurchaseOrder, po_ids),
        "receipts": _by_id(session, GoodsReceipt, receipt_ids),
        "invoices": _by_id(session, SupplierInvoice, invoice_ids),
        "products": _by_id(session, Product, product_ids),
        "reviews": {case.reconciliation_exception_id: case_view(case) for case in reviews},
    }


def _by_id(session: Session, model: type[Any], ids: set[int]) -> dict[int, Any]:
    if not ids:
        return {}
    rows = session.scalars(select(model).where(model.id.in_(ids))).all()
    return {row.id: row for row in rows}


def _ref(row: Any, number_attr: str) -> dict[str, Any]:
    return {"id": row.id, "number": getattr(row, number_attr)}
