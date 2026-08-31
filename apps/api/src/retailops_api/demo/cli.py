"""Build the local demo dataset against the configured database.

    make demo

Or, from ``apps/api``:

    uv run retailops-demo
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

from retailops_api.core.config import get_settings
from retailops_api.db.session import get_session_factory
from retailops_api.demo.bootstrap import bootstrap_demo
from retailops_api.demo.paths import default_demo_paths
from retailops_api.demo.performance import measure_local_steps
from retailops_api.demo.schema import upgrade_schema
from retailops_api.synthetic.config import ScalePreset


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        if args.command == "measure":
            return _measure(args)
        return _run(args)
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="retailops-demo",
        description=(
            "Apply migrations, load the reference catalog, generate and ingest "
            "sales, persist a demand forecast, ingest supplier sheets, create "
            "purchase-order scenarios and open human-review cases."
        ),
    )
    parser.add_argument(
        "--preset",
        choices=[item.value for item in ScalePreset],
        default=ScalePreset.development.value,
        help="Sales-history scale (default: development).",
    )
    parser.add_argument(
        "--skip-migrate",
        action="store_true",
        help="Assume the schema is already current.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Override the synthetic CSV directory.",
    )
    parser.add_argument(
        "--storage",
        type=Path,
        help="Override the local document root.",
    )
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("run", help="Build the dataset (default).")
    sub.add_parser("measure", help="Print wall-clock samples for the tiny local steps.")
    return parser.parse_args(argv)


def _run(args: argparse.Namespace) -> int:
    if not args.skip_migrate:
        upgrade_schema()
        print("schema is at Alembic head")
    paths = default_demo_paths()
    if args.output is not None:
        paths = replace(paths, synthetic=args.output)
    storage = args.storage
    if storage is None:
        configured = get_settings().document_storage_root.strip()
        storage = Path(configured) if configured else paths.documents
    with get_session_factory()() as session:
        try:
            report = bootstrap_demo(
                session, paths=paths, preset=args.preset, documents_root=storage
            )
            session.commit()
        except Exception:
            session.rollback()
            raise
    print(report.format_text())
    return 0


def _measure(args: argparse.Namespace) -> int:
    paths = default_demo_paths()
    output = args.output or paths.synthetic
    work = default_demo_paths().forecasts / "perf-timing"
    with get_session_factory()() as session:
        try:
            timings = measure_local_steps(session, output, work=work)
            session.commit()
        except Exception:
            session.rollback()
            raise
    failed = False
    for step in timings:
        flag = "ok" if step.ok else "SLOW"
        print(f"{step.name:14} {step.seconds:7.3f}s  limit={step.limit:.1f}s  {flag}")
        if not step.ok:
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
