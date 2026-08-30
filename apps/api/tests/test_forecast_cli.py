from pathlib import Path

from retailops_api.forecasting.cli import main


def test_cli_benchmark_writes_the_frame_and_the_report(tmp_path: Path) -> None:
    code = main(
        [
            "--preset",
            "tiny",
            "--start-date",
            "2025-01-06",
            "--end-date",
            "2025-05-25",
            "--min-train-periods",
            "8",
            "--test-periods",
            "4",
            "--validation-periods",
            "4",
            "--output",
            str(tmp_path),
            "benchmark",
        ]
    )

    assert code == 0
    assert (tmp_path / "forecast_frame.csv").is_file()
    assert (tmp_path / "benchmark.json").is_file()
    assert (tmp_path / "benchmark.md").is_file()
    header = (tmp_path / "forecast_frame.csv").read_text(encoding="utf-8").splitlines()[0]
    assert header == "store_code,category_code,period_start,target"


def test_cli_frame_writes_only_the_csv(tmp_path: Path) -> None:
    code = main(
        [
            "--preset",
            "tiny",
            "--start-date",
            "2025-01-06",
            "--end-date",
            "2025-02-02",
            "--output",
            str(tmp_path),
            "frame",
        ]
    )

    assert code == 0
    assert (tmp_path / "forecast_frame.csv").is_file()
    assert not (tmp_path / "benchmark.json").exists()
