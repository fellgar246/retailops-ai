"""Run a deterministic three-way match for one purchase order or invoice.

    make reconcile supplier=SUP-BEVCO invoice=INV-1001

Or, from ``apps/api``:

    uv run retailops-reconcile --supplier SUP-BEVCO --invoice INV-1001
    uv run retailops-reconcile --supplier SUP-BEVCO --po PO-1001
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from decimal import Decimal

from retailops_api.db.session import get_session_factory
from retailops_api.procurement.orchestrate import reconcile
from retailops_api.procurement.types import (
    ReconciliationError,
    ReconciliationResult,
    ReconciliationScope,
    ReconciliationTolerances,
)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        scope = ReconciliationScope(
            supplier_code=args.supplier,
            po_number=args.po,
            invoice_number=args.invoice,
        )
        tolerances = ReconciliationTolerances(
            quantity_tolerance=args.quantity_tolerance,
            monetary_tolerance=Decimal(args.monetary_tolerance),
            price_percent_tolerance=Decimal(args.price_percent_tolerance),
        )
        with get_session_factory()() as session:
            try:
                result = reconcile(session, scope, tolerances=tolerances)
                session.commit()
            except Exception:
                session.rollback()
                raise
        _print_result(result)
        return 0
    except ReconciliationError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="retailops-reconcile",
        description=(
            "Match a supplier invoice and its goods receipts against the "
            "purchase order, apply configured tolerances and persist exceptions."
        ),
    )
    parser.add_argument("--supplier", required=True, help="Supplier business code, e.g. SUP-BEVCO.")
    parser.add_argument("--invoice", help="Invoice number unique to that supplier.")
    parser.add_argument("--po", help="Purchase order number unique to that supplier.")
    parser.add_argument(
        "--quantity-tolerance",
        type=int,
        default=0,
        help="Whole units of quantity difference that still pass (default 0).",
    )
    parser.add_argument(
        "--monetary-tolerance",
        default="0.0000",
        help="Absolute cost difference that still passes (default 0.0000).",
    )
    parser.add_argument(
        "--price-percent-tolerance",
        default="0.0000",
        help="Percent of PO unit cost that still passes (default 0.0000).",
    )
    return parser.parse_args(argv)


def _print_result(result: ReconciliationResult) -> None:
    reused = " reused" if result.reused else ""
    print(
        f"run={result.run_id}  scope={result.scope_key}  version={result.version}{reused}  "
        f"exceptions={result.exception_count}  "
        f"error={result.error_count} warning={result.warning_count} info={result.info_count}  "
        f"impact={result.total_financial_impact}"
    )
    for item in result.exceptions:
        print(
            f"  {item.severity.value} {item.code}: {item.message} "
            f"(expected {item.expected_value}, actual {item.actual_value}, "
            f"impact {item.financial_impact})"
        )


if __name__ == "__main__":
    raise SystemExit(main())
