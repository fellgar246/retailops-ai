"""The generate command writes a valid snapshot without a database."""

from pathlib import Path

from retailops_api.dataset.snapshot import load_dataset
from retailops_api.dataset.validate import assert_valid
from retailops_api.ingestion.cli import main


def test_cli_generate_writes_a_valid_tiny_snapshot(tmp_path: Path) -> None:
    code = main(["--preset", "tiny", "--output", str(tmp_path), "generate"])

    assert code == 0
    dataset = load_dataset(tmp_path)
    assert_valid(dataset)
    assert dataset.sales
    assert (tmp_path / "manifest.json").is_file()
