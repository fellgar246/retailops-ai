from pathlib import Path

from retailops_api.review.cli import main


def test_cli_writes_the_evaluation_report(tmp_path: Path) -> None:
    code = main(["--output", str(tmp_path)])

    assert code == 0
    assert (tmp_path / "evaluation.json").is_file()
    assert (tmp_path / "evaluation.md").is_file()


def test_cli_missing_dataset_is_an_error(tmp_path: Path) -> None:
    code = main(["--dataset", str(tmp_path / "missing.jsonl"), "--output", str(tmp_path)])

    assert code == 1
