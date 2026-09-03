import pytest

from retailops_api.documents.s3 import S3DocumentStorage
from retailops_api.documents.storage import sha256_hex
from retailops_api.documents.types import StorageError
from tests.aws_fakes import FakeS3


def test_s3_save_put_get_head_and_checksum() -> None:
    store = S3DocumentStorage(FakeS3(), bucket="docs", prefix="documents")
    stored = store.save(b"hello", filename="offer.csv", media_type="text/csv")

    assert store.exists(stored.key)
    assert store.read(stored.key) == b"hello"
    assert stored.checksum == sha256_hex(b"hello")
    assert stored.filename == "offer.csv"
    meta = store.metadata(stored.key)
    assert meta.checksum == stored.checksum
    assert meta.filename == "offer.csv"
    assert meta.media_type == "text/csv"
    assert meta.size == 5
    with store.open(stored.key) as handle:
        assert handle.read() == b"hello"


def test_s3_filename_is_not_used_as_the_object_key() -> None:
    client = FakeS3()
    store = S3DocumentStorage(client, bucket="docs", prefix="documents")
    stored = store.save(b"x", filename="../secret.csv", media_type="text/csv")

    assert stored.filename == "secret.csv"
    assert ("docs", "secret.csv") not in client.objects
    assert all("secret.csv" not in key for _, key in client.objects)
    assert ("docs", f"documents/{stored.key}/source/payload") in client.objects


def test_s3_rejects_illegal_keys() -> None:
    store = S3DocumentStorage(FakeS3(), bucket="docs")
    with pytest.raises(StorageError, match="invalid storage key"):
        store.read("../etc/passwd")
    with pytest.raises(StorageError, match="invalid storage key"):
        store.exists("not-a-key")


def test_s3_delete_and_missing_key() -> None:
    store = S3DocumentStorage(FakeS3(), bucket="docs")
    stored = store.save(b"bye", filename="a.csv", media_type="text/csv")
    store.delete(stored.key)
    assert not store.exists(stored.key)
    with pytest.raises(StorageError, match="unknown storage key"):
        store.read(stored.key)
    with pytest.raises(StorageError, match="unknown storage key"):
        store.metadata(stored.key)
