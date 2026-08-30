"""Write reconciliation runs and their exceptions. Does not commit."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from retailops_api.dataset.contract import quantize_money
from retailops_api.domain.models import ReconciliationException, ReconciliationRun
from retailops_api.domain.models.reconciliation import ExceptionSeverity
from retailops_api.procurement.types import (
    ProposedException,
    ReconciliationDraft,
    ReconciliationResult,
    SelectedRecords,
)


def input_fingerprint(records: SelectedRecords, draft: ReconciliationDraft) -> str:
    payload = {
        "orders": [
            {
                "id": order.id,
                "number": order.number,
                "currency": order.currency,
                "lines": [
                    {
                        "id": line.id,
                        "product_id": line.product_id,
                        "ordered_quantity": line.ordered_quantity,
                        "unit_cost": str(line.unit_cost),
                        "tax_rate": str(line.tax_rate),
                        "line_total": str(line.line_total),
                    }
                    for line in order.lines
                ],
            }
            for order in records.purchase_orders
        ],
        "receipts": [
            {
                "id": receipt.id,
                "number": receipt.number,
                "lines": [
                    {
                        "id": line.id,
                        "product_id": line.product_id,
                        "received_quantity": line.received_quantity,
                        "purchase_order_line_id": line.purchase_order_line_id,
                    }
                    for line in receipt.lines
                ],
            }
            for receipt in records.receipts
        ],
        "invoices": [
            {
                "id": invoice.id,
                "number": invoice.number,
                "currency": invoice.currency,
                "lines": [
                    {
                        "id": line.id,
                        "product_id": line.product_id,
                        "supplier_sku": line.supplier_sku,
                        "ean": line.ean,
                        "invoiced_quantity": line.invoiced_quantity,
                        "unit_cost": str(line.unit_cost),
                        "tax_rate": str(line.tax_rate),
                        "line_total": str(line.line_total),
                    }
                    for line in invoice.lines
                ],
            }
            for invoice in records.invoices
        ],
        "tolerances": draft.tolerances.to_dict(),
    }
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def latest_run(session: Session, scope_key: str) -> ReconciliationRun | None:
    return session.scalar(
        select(ReconciliationRun)
        .options(selectinload(ReconciliationRun.exceptions))
        .where(ReconciliationRun.scope_key == scope_key)
        .order_by(ReconciliationRun.version.desc())
        .limit(1)
    )


def persist_run(
    session: Session,
    *,
    scope_key: str,
    version: int,
    fingerprint: str,
    generated_at: datetime,
    records: SelectedRecords,
    draft: ReconciliationDraft,
) -> ReconciliationRun:
    counts = _counts(draft.exceptions)
    run = ReconciliationRun(
        scope_key=scope_key,
        version=version,
        input_fingerprint=fingerprint,
        generated_at=generated_at,
        purchase_order_count=len(records.purchase_orders),
        goods_receipt_count=len(records.receipts),
        supplier_invoice_count=len(records.invoices),
        exception_count=counts["exception_count"],
        error_count=counts["error_count"],
        warning_count=counts["warning_count"],
        info_count=counts["info_count"],
        total_financial_impact=counts["total_financial_impact"],
        tolerances=draft.tolerances.to_dict(),
    )
    session.add(run)
    session.flush()
    for item in draft.exceptions:
        session.add(
            ReconciliationException(
                reconciliation_run_id=run.id,
                code=item.code,
                severity=item.severity.value,
                purchase_order_id=item.purchase_order_id,
                purchase_order_line_id=item.purchase_order_line_id,
                goods_receipt_id=item.goods_receipt_id,
                goods_receipt_line_id=item.goods_receipt_line_id,
                supplier_invoice_id=item.supplier_invoice_id,
                supplier_invoice_line_id=item.supplier_invoice_line_id,
                product_id=item.product_id,
                expected_value=item.expected_value,
                actual_value=item.actual_value,
                financial_impact=item.financial_impact,
                message=item.message,
            )
        )
    session.flush()
    session.refresh(run)
    return run


def result_from_run(run: ReconciliationRun, *, reused: bool) -> ReconciliationResult:
    proposed = tuple(_proposed(item) for item in run.exceptions)
    return ReconciliationResult(
        run_id=run.id,
        scope_key=run.scope_key,
        version=run.version,
        reused=reused,
        input_fingerprint=run.input_fingerprint,
        purchase_order_count=run.purchase_order_count,
        goods_receipt_count=run.goods_receipt_count,
        supplier_invoice_count=run.supplier_invoice_count,
        exception_count=run.exception_count,
        error_count=run.error_count,
        warning_count=run.warning_count,
        info_count=run.info_count,
        total_financial_impact=run.total_financial_impact,
        exceptions=proposed,
    )


def _proposed(row: ReconciliationException) -> ProposedException:
    return ProposedException(
        code=row.code,
        severity=ExceptionSeverity(row.severity),
        message=row.message,
        expected_value=row.expected_value,
        actual_value=row.actual_value,
        financial_impact=row.financial_impact,
        purchase_order_id=row.purchase_order_id,
        purchase_order_line_id=row.purchase_order_line_id,
        goods_receipt_id=row.goods_receipt_id,
        goods_receipt_line_id=row.goods_receipt_line_id,
        supplier_invoice_id=row.supplier_invoice_id,
        supplier_invoice_line_id=row.supplier_invoice_line_id,
        product_id=row.product_id,
    )


def _counts(exceptions: Sequence[ProposedException]) -> dict[str, int | Decimal]:
    error = sum(1 for item in exceptions if item.severity is ExceptionSeverity.error)
    warning = sum(1 for item in exceptions if item.severity is ExceptionSeverity.warning)
    info = sum(1 for item in exceptions if item.severity is ExceptionSeverity.info)
    impact = sum((item.financial_impact for item in exceptions), Decimal("0"))
    return {
        "exception_count": len(exceptions),
        "error_count": error,
        "warning_count": warning,
        "info_count": info,
        "total_financial_impact": quantize_money(impact),
    }
