from datetime import date
from pathlib import Path

from retailops_api.dataset.contract import Dataset
from retailops_api.dataset.snapshot import dataset_checksum
from retailops_api.forecasting.benchmark import (
    BenchmarkConfig,
    DatasetSummary,
    render_markdown,
    report_to_dict,
    run_benchmark,
    write_benchmark,
)
from retailops_api.forecasting.frame import ForecastFrame, build_forecast_frame
from retailops_api.synthetic.config import GeneratorConfig
from retailops_api.synthetic.generate import generate_dataset


def _frame() -> tuple[Dataset, ForecastFrame]:
    dataset = generate_dataset(
        GeneratorConfig.from_preset(
            "tiny",
            start_date=date(2025, 1, 6),
            end_date=date(2025, 5, 25),
        )
    )
    return dataset, build_forecast_frame(dataset)


def _summary(dataset: Dataset) -> DatasetSummary:
    dates = [row.business_date for row in dataset.sales]
    frame = build_forecast_frame(dataset)
    return DatasetSummary(
        source="synthetic:tiny",
        start_date=min(dates),
        end_date=max(dates),
        checksum=dataset_checksum(dataset),
        complete_weeks=len(frame.periods()),
        entity_count=len(frame.entities()),
        row_count=len(frame.rows),
    )


def test_benchmark_is_deterministic_and_names_every_baseline() -> None:
    dataset, frame = _frame()
    summary = _summary(dataset)
    config = BenchmarkConfig(min_train_periods=8, test_periods=4, validation_periods=4)
    first = run_benchmark(frame, dataset=summary, config=config)
    second = run_benchmark(frame, dataset=summary, config=config)

    assert [result.model_id for result in first.results] == [
        "naive",
        "seasonal_naive",
        "moving_average",
    ]
    assert report_to_dict(first) == report_to_dict(second)
    payload = report_to_dict(first)
    assert payload["backtest"]["strategy"] == "rolling-origin"
    assert payload["problem"]["id"] == "weekly_category_store_demand"
    assert payload["holdout"]["train_end"] < payload["holdout"]["validation_end"]


def test_seasonal_naive_matches_naive_when_the_year_lag_is_unavailable() -> None:
    dataset, frame = _frame()
    report = run_benchmark(
        frame,
        dataset=_summary(dataset),
        config=BenchmarkConfig(
            seasonal_lag=52,
            min_train_periods=8,
            test_periods=4,
            validation_periods=4,
        ),
    )
    by_id = {result.model_id: result for result in report.results}

    assert by_id["naive"].overall == by_id["seasonal_naive"].overall


def test_markdown_documents_metrics_cutoffs_and_the_backtest() -> None:
    dataset, frame = _frame()
    report = run_benchmark(
        frame,
        dataset=_summary(dataset),
        config=BenchmarkConfig(min_train_periods=8, test_periods=4, validation_periods=4),
    )
    text = render_markdown(report)

    assert "Weekly category demand per store" in text
    assert "WAPE" in text
    assert "Walk-forward" in text
    assert "rolling-origin" in text
    assert "Train ends:" in text
    assert "`naive`" in text
    assert "zero" in text.lower()


def test_write_benchmark_creates_json_and_markdown(tmp_path: Path) -> None:
    dataset, frame = _frame()
    report = run_benchmark(
        frame,
        dataset=_summary(dataset),
        config=BenchmarkConfig(min_train_periods=8, test_periods=4, validation_periods=4),
    )
    write_benchmark(report, tmp_path)

    assert (tmp_path / "benchmark.json").is_file()
    assert (tmp_path / "benchmark.md").is_file()
    assert "mae" in (tmp_path / "benchmark.json").read_text(encoding="utf-8")
