"""Score a reviewer against the versioned evaluation cases.

    make review-eval

Or, from ``apps/api``:

    uv run retailops-review-eval
    uv run retailops-review-eval --provider bedrock --stamp
    uv run retailops-review-eval --compare
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from retailops_api.core.adapters import ai_reviewer_for
from retailops_api.core.config import get_settings
from retailops_api.review.contract import AIReviewer
from retailops_api.review.dataset import DATASET_VERSION, EvaluationDataset, load_dataset
from retailops_api.review.evaluate import (
    EVALUATION_JSON,
    EVALUATION_MARKDOWN,
    EvaluationReport,
    evaluate,
    write_comparison,
    write_evaluation,
)
from retailops_api.review.mock import MockAIReviewer
from retailops_api.review.paths import default_review_output


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        dataset = load_dataset(args.dataset, version=args.version)
        output = args.output or default_review_output()
        if args.compare:
            mock_report = evaluate(MockAIReviewer(dataset.fixtures()), dataset)
            live = _live_reviewer()
            live_report = evaluate(
                live,
                dataset,
                region=_reviewer_region(live),
                model_id=_reviewer_model(live),
            )
            mock_dir = write_evaluation(mock_report, output / "mock", stamp=True)
            live_dir = write_evaluation(live_report, output / "bedrock", stamp=True)
            comparison = write_comparison(mock_report, live_report, output / "comparisons")
            _print_report(mock_report, mock_dir)
            _print_report(live_report, live_dir)
            print(f"wrote {comparison}")
            return 0
        reviewer = _reviewer_for(args.provider, dataset)
        report = evaluate(
            reviewer,
            dataset,
            region=_reviewer_region(reviewer),
            model_id=_reviewer_model(reviewer),
        )
        stamp = args.stamp or args.provider == "bedrock"
        written = write_evaluation(report, output, stamp=stamp)
        _print_report(report, written)
        return 0
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


def _reviewer_for(provider: str, dataset: EvaluationDataset) -> AIReviewer:
    if provider == "bedrock":
        return _live_reviewer()
    return MockAIReviewer(dataset.fixtures())


def _live_reviewer() -> AIReviewer:
    settings = get_settings()
    aws = settings.aws_config()
    if not aws.bedrock_enabled():
        raise ValueError(
            "Bedrock is disabled; set AWS_ENABLED=true and "
            "BEDROCK_ENABLED=true (or AWS_USE_BEDROCK=true)"
        )
    return ai_reviewer_for(settings)


def _reviewer_model(reviewer: AIReviewer) -> str | None:
    model = getattr(reviewer, "model_id", None)
    return str(model) if model else None


def _reviewer_region(reviewer: AIReviewer) -> str | None:
    region = getattr(reviewer, "region", None)
    return str(region) if region else None


def _print_report(report: EvaluationReport, output: Path) -> None:
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


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="retailops-review-eval",
        description=(
            "Run a reviewer against the versioned evaluation cases and "
            "write a machine-readable report. Mock is the default so "
            "local checks never call AWS."
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
    parser.add_argument(
        "--provider",
        choices=("mock", "bedrock"),
        default="mock",
        help="Reviewer implementation. bedrock requires AWS_ENABLED and BEDROCK_ENABLED.",
    )
    parser.add_argument(
        "--stamp",
        action="store_true",
        help="Write into a timestamped subdirectory so prior reports are kept.",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Score mock and Bedrock, write both reports, and emit a comparison.",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
