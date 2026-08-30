from pathlib import Path

import pytest

from retailops_api.documents.storage import LocalDocumentStorage, sha256_hex
from retailops_api.documents.types import StorageError


def test_save_assigns_a_generated_key_and_checksum(tmp_path: Path) -> None:
    store = LocalDocumentStorage(tmp_path)
    stored = store.save(b"hello", filename="offer.csv", media_type="text/csv")

    assert store.exists(stored.key)
    assert store.read(stored.key) == b"hello"
    assert stored.checksum == sha256_hex(b"hello")
    assert stored.filename == "offer.csv"
    assert stored.size == 5
    meta = store.metadata(stored.key)
    assert meta.checksum == stored.checksum
    assert meta.filename == "offer.csv"
    assert meta.media_type == "text/csv"


def test_filename_is_not_used_as_a_path(tmp_path: Path) -> None:
    store = LocalDocumentStorage(tmp_path)
    stored = store.save(b"x", filename="../secret.csv", media_type="text/csv")

    assert stored.filename == "secret.csv"
    assert not (tmp_path / "secret.csv").exists()
    assert (tmp_path / stored.key).is_file()
    with store.open(stored.key) as handle:
        assert handle.read() == b"x"


def test_path_traversal_keys_are_rejected(tmp_path: Path) -> None:
    store = LocalDocumentStorage(tmp_path)

    with pytest.raises(StorageError, match="invalid storage key"):
        store.read("../etc/passwd")
    with pytest.raises(StorageError, match="invalid storage key"):
        store.exists("abc/../" + "d" * 32)
    with pytest.raises(StorageError, match="invalid storage key"):
        store.delete("not-a-key")


def test_delete_removes_object_and_sidecar(tmp_path: Path) -> None:
    store = LocalDocumentStorage(tmp_path)
    stored = store.save(b"bye", filename="a.csv", media_type="text/csv")
    sidecar = tmp_path / f"{stored.key}.meta.json"
    assert sidecar.is_file()

    store.delete(stored.key)

    assert not store.exists(stored.key)
    assert not sidecar.exists()
    with pytest.raises(StorageError, match="unknown storage key"):
        store.read(stored.key)
