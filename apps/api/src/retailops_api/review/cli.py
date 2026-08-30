"""Score a reviewer against the versioned evaluation cases.

    make review-eval

Or, from ``apps/api``:

    uv run retailops-review-eval
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from retailops_api.review.dataset import DATASET_VERSION, load_dataset
from retailops_api.review.evaluate import (
    EVALUATION_JSON,
    EVALUATION_MARKDOWN,
    evaluate,
    write_evaluation,
)
from retailops_api.review.mock import MockAIReviewer
from retailops_api.review.paths import default_review_output


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        dataset = load_dataset(args.dataset, version=args.version)
        reviewer = MockAIReviewer(dataset.fixtures())
        report = evaluate(reviewer, dataset)
        output = args.output or default_review_output()
        write_evaluation(report, output)
        print(
            f"wrote {output / EVALUATION_JSON}  {output / EVALUATION_MARKDOWN}  "
            f"cases={report.metrics.case_count}  reviewer={report.reviewer}"
        )
        metrics = report.metrics
        print(
            f"  schema_validity={metrics.schema_validity:.4f}  "
            f"classification={metrics.classification_accuracy:.4f}  "
            f"action={metrics.recommended_action_accuracy:.4f}  "
            f"confidence={metrics.confidence_presence:.4f}  "
            f"provider_failure={metrics.provider_failure_rate:.4f}"
        )
        return 0
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="retailops-review-eval",
        description=(
            "Run the mock reviewer against the versioned evaluation cases and "
            "write a machine-readable report. Any reviewer that implements the "
            "same contract can be scored the same way."
        ),
    )
    parser.add_argument(
        "--version",
        default=DATASET_VERSION,
        help=f"Packaged dataset version (default {DATASET_VERSION}).",
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        help="Directory or JSONL file of cases (default: the packaged dataset).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Directory for evaluation.json and evaluation.md (default: <repo>/data/reviews).",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
