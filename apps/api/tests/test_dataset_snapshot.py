"""CSV snapshots round-trip and the checksum is stable for the same seed."""

from pathlib import Path

from retailops_api.dataset.contract import Dataset
from retailops_api.dataset.snapshot import dataset_checksum, load_dataset, write_dataset
from retailops_api.dataset.validate import DatasetValidationError, assert_valid
from retailops_api.synthetic.config import GeneratorConfig
from retailops_api.synthetic.generate import generate_dataset


def _tiny_dataset(**overrides: object) -> Dataset:
    return generate_dataset(GeneratorConfig.from_preset("tiny", **overrides))


def test_the_same_seed_produces_the_same_checksum() -> None:
    first = dataset_checksum(_tiny_dataset())
    second = dataset_checksum(_tiny_dataset())

    assert first == second
    assert len(first) == 64


def test_a_different_seed_produces_a_different_checksum() -> None:
    assert dataset_checksum(_tiny_dataset(seed=1)) != dataset_checksum(_tiny_dataset(seed=2))


def test_writing_and_reading_a_snapshot_preserves_the_dataset(tmp_path: Path) -> None:
    original = _tiny_dataset()
    checksum = write_dataset(original, tmp_path)

    loaded = load_dataset(tmp_path)
    assert_valid(loaded)
    assert dataset_checksum(loaded) == checksum
    assert loaded.catalog == original.catalog
    assert loaded.sales == original.sales
    assert loaded.calendar == original.calendar
    assert (tmp_path / "manifest.json").is_file()
    assert (tmp_path / "daily_sales.csv").is_file()
    assert (tmp_path / "calendar.csv").is_file()


def test_a_missing_file_is_an_actionable_validation_error(tmp_path: Path) -> None:
    write_dataset(_tiny_dataset(), tmp_path)
    (tmp_path / "products.csv").unlink()

    try:
        load_dataset(tmp_path)
    except DatasetValidationError as error:
        assert any("products.csv" in issue.message for issue in error.issues)
    else:
        raise AssertionError("expected DatasetValidationError")


def test_a_missing_column_is_an_actionable_validation_error(tmp_path: Path) -> None:
    write_dataset(_tiny_dataset(), tmp_path)
    path = tmp_path / "stores.csv"
    path.write_text("code,name,region\nST-001,X,Central\n", encoding="utf-8")

    try:
        load_dataset(tmp_path)
    except DatasetValidationError as error:
        message = " ".join(issue.message for issue in error.issues)
        assert "store_type" in message
    else:
        raise AssertionError("expected DatasetValidationError")
