from pathlib import Path

from retailops_api.documents.cli import main


def test_cli_missing_file_is_an_error(tmp_path: Path) -> None:
    code = main(["--supplier", "SUP-BEVCO", "--file", str(tmp_path / "missing.csv")])

    assert code == 1
