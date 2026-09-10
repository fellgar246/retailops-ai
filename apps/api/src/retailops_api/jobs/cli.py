"""Run the job worker.

    make worker

Or, from ``apps/api``:

    uv run retailops-worker --kind document_intake
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence

from retailops_api.domain.models.job import JobKind
from retailops_api.jobs.worker import Worker, install_signal_handlers


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    kinds = tuple(JobKind(kind) for kind in args.kind)
    worker = Worker(kinds=kinds)
    install_signal_handlers(worker)
    try:
        processed = worker.run_forever(max_iterations=args.max_iterations)
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"processed {processed} job(s)")
    return 0


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="retailops-worker",
        description="Claim and run queued work until stopped.",
    )
    parser.add_argument(
        "--kind",
        action="append",
        default=[],
        choices=[kind.value for kind in JobKind],
        help="Only handle this kind. Repeatable. Omit to handle every kind.",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        help="Stop after this many passes. Useful for a one-shot drain.",
    )
    parser.add_argument("--log-level", default="info")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
