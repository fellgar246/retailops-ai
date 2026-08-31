"""One command fills catalog, sales, a forecast, sheets, matches and reviews."""

from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from retailops_api.demo.cli import _parse_args, main
from retailops_api.domain.models import (
    ForecastRun,
    ReconciliationException,
    ReconciliationRun,
    ReviewCase,
    SalesRecord,
    SupplierDocument,
)
from tests.demo_support import load_demo


def test_bootstrap_fills_every_demo_surface(session: Session, tmp_path: Path) -> None:
    report = load_demo(session, tmp_path)

    assert session.scalar(select(func.count()).select_from(SalesRecord)) or 0 > 0
    assert session.scalar(select(func.count()).select_from(SupplierDocument)) == 3
    assert session.scalar(select(func.count()).select_from(ForecastRun)) == 1
    assert session.scalar(select(func.count()).select_from(ReconciliationRun)) == 2
    assert session.scalar(select(func.count()).select_from(ReconciliationException)) or 0 > 0
    assert session.scalar(select(func.count()).select_from(ReviewCase)) or 0 > 0
    assert report.forecast_run_id is not None
    assert len(report.document_ids) == 3
    assert len(report.reconciliation_run_ids) == 2
    assert report.review_case_ids


def test_bootstrap_is_safe_to_re_run(session: Session, tmp_path: Path) -> None:
    first = load_demo(session, tmp_path)
    session.commit()
    second = load_demo(session, tmp_path)

    assert second.sales.duplicate_count == first.sales.rows_accepted
    assert session.scalar(select(func.count()).select_from(SupplierDocument)) == 3
    assert session.scalar(select(func.count()).select_from(ForecastRun)) == 1
    assert session.scalar(select(func.count()).select_from(ReconciliationRun)) == 2
    assert set(second.review_case_ids) == set(first.review_case_ids)


def test_cli_help_describes_the_dataset_command(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exited:
        main(["--help"])
    assert exited.value.code == 0
    output = capsys.readouterr().out.lower()
    assert "catalog" in output
    assert "review" in output


def test_cli_accepts_the_timing_command() -> None:
    args = _parse_args(["measure"])
    assert args.command == "measure"
