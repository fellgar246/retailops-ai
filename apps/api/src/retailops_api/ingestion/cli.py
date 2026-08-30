"""Generate a synthetic retail dataset and ingest it.

Regenerate the development dataset and load it into the configured database:

    make synthetic

Or, from ``apps/api``:

    uv run retailops-synthetic
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime
from pathlib import Path

from retailops_api.dataset.snapshot import MANIFEST_FILE, load_dataset, write_dataset
from retailops_api.dataset.validate import assert_valid
from retailops_api.db.session import get_session_factory
from retailops_api.ingestion.catalog import ingest_catalog
from retailops_api.ingestion.report import IngestionRunReport
from retailops_api.ingestion.sales import ingest_sales
from retailops_api.synthetic.config import GeneratorConfig, ScalePreset
from retailops_api.synthetic.generate import generate_dataset

REPORT_FILE = "ingestion_report.json"


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    command = args.command or "run"
    try:
        if command == "generate":
            _generate(args)
            return 0
        if command == "ingest":
            _print_report(_ingest_from_files(args))
            return 0
        _print_report(_run(args))
        return 0
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="retailops-synthetic",
        description="Generate and ingest a deterministic synthetic retail dataset.",
    )
    parser.add_argument(
        "--preset",
        choices=[preset.value for preset in ScalePreset],
        default=ScalePreset.development.value,
        help="Scale of the generated dataset (default: development).",
    )
    parser.add_argument("--seed", type=int, help="Override the generator seed.")
    parser.add_argument("--start-date", type=_date, help="First trading day (YYYY-MM-DD).")
    parser.add_argument("--end-date", type=_date, help="Last trading day (YYYY-MM-DD).")
    parser.add_argument("--stores", type=int, dest="store_count")
    parser.add_argument("--products", type=int, dest="product_count")
    parser.add_argument("--suppliers", type=int, dest="supplier_count")
    parser.add_argument("--categories", type=int, dest="category_count")
    parser.add_argument("--promotion-probability", type=float)
    parser.add_argument("--stockout-probability", type=float)
    parser.add_argument(
        "--holiday",
        action="append",
        type=_date,
        default=[],
        help="Extra holiday (YYYY-MM-DD). Repeatable.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Directory for CSV files (default: <repo>/data/synthetic).",
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Directory to ingest from (defaults to --output).",
    )
    parser.add_argument("--source", help="Override the source label written on the run report.")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("generate", help="Write the CSV snapshot without touching the database.")
    sub.add_parser("ingest", help="Ingest an existing CSV snapshot.")
    sub.add_parser("run", help="Generate, validate, write and ingest (default).")
    return parser.parse_args(argv)


def _generate(args: argparse.Namespace) -> str:
    config = _config_from_args(args)
    output = _output_dir(args)
    dataset = generate_dataset(config)
    assert_valid(dataset)
    checksum = write_dataset(
        dataset,
        output,
        extra_manifest={"preset": config.preset, "config": config.model_dump(mode="json")},
    )
    print(f"wrote {output}  checksum={checksum}  sales_rows={len(dataset.sales)}")
    return checksum


def _run(args: argparse.Namespace) -> IngestionRunReport:
    started = datetime.now(UTC)
    config = _config_from_args(args)
    output = _output_dir(args)
    dataset = generate_dataset(config)
    assert_valid(dataset)
    checksum = write_dataset(
        dataset,
        output,
        extra_manifest={"preset": config.preset, "config": config.model_dump(mode="json")},
    )
    source = args.source or f"synthetic:{config.preset or 'custom'}"
    report = _ingest_dataset(dataset, source=source, started=started, checksum=checksum)
    report.write_json(output / REPORT_FILE)
    return report


def _ingest_from_files(args: argparse.Namespace) -> IngestionRunReport:
    started = datetime.now(UTC)
    directory = args.input or _output_dir(args)
    dataset = load_dataset(directory)
    assert_valid(dataset)
    checksum = None
    manifest = directory / MANIFEST_FILE
    if manifest.is_file():
        checksum = json.loads(manifest.read_text(encoding="utf-8")).get("checksum")
    source = args.source or f"file:{directory}"
    report = _ingest_dataset(dataset, source=source, started=started, checksum=checksum)
    report.write_json(directory / REPORT_FILE)
    return report


def _ingest_dataset(
    dataset: object,
    *,
    source: str,
    started: datetime,
    checksum: str | None,
) -> IngestionRunReport:
    from retailops_api.dataset.contract import Dataset as DatasetType

    assert isinstance(dataset, DatasetType)
    with get_session_factory()() as session:
        try:
            catalog_result = ingest_catalog(session, dataset.catalog)
            sales_stats = ingest_sales(session, dataset.sales)
            session.commit()
        except Exception:
            session.rollback()
            raise
    return IngestionRunReport(
        source=source,
        run_id=uuid.uuid4().hex,
        started_at=started,
        finished_at=datetime.now(UTC),
        rows_read=sales_stats.rows_read,
        rows_accepted=sales_stats.rows_accepted,
        rows_rejected=sales_stats.rows_rejected,
        duplicate_count=sales_stats.duplicate_count,
        validation_errors=sales_stats.validation_errors,
        catalog=catalog_result,
        checksum=checksum,
    )


def _config_from_args(args: argparse.Namespace) -> GeneratorConfig:
    overrides: dict[str, object] = {}
    for field in (
        "seed",
        "start_date",
        "end_date",
        "store_count",
        "product_count",
        "supplier_count",
        "category_count",
        "promotion_probability",
        "stockout_probability",
    ):
        value = getattr(args, field, None)
        if value is not None:
            overrides[field] = value
    if args.holiday:
        overrides["holidays"] = tuple(args.holiday)
    return GeneratorConfig.from_preset(args.preset, **overrides)


def _output_dir(args: argparse.Namespace) -> Path:
    if args.output is not None:
        return Path(args.output)
    return find_repo_root() / "data" / "synthetic"


def find_repo_root() -> Path:
    for candidate in (Path.cwd(), *Path.cwd().parents):
        if (candidate / "apps" / "api" / "pyproject.toml").exists():
            return candidate
    return Path.cwd()


def _date(value: str) -> date:
    return date.fromisoformat(value)


def _print_report(report: IngestionRunReport) -> None:
    print(report.format_text())


if __name__ == "__main__":
    raise SystemExit(main())
