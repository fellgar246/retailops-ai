import pytest

from retailops_api.documents.keys import (
    DEFAULT_DOCUMENTS_PREFIX,
    LIVE_SMOKE_PREFIX,
    is_safe_object_key,
    source_object_key,
    supplier_source_object_key,
)
from retailops_api.documents.types import StorageError


def test_source_object_key_is_reconstructable() -> None:
    key = "a" * 32
    assert source_object_key(key) == f"{DEFAULT_DOCUMENTS_PREFIX}/{key}/source/payload"
    assert source_object_key(key, prefix=LIVE_SMOKE_PREFIX) == f"live-smoke/{key}/source/payload"


def test_source_object_key_rejects_path_traversal() -> None:
    with pytest.raises(StorageError):
        source_object_key("../" + "a" * 30)
    with pytest.raises(StorageError):
        source_object_key("a" * 32, prefix="../etc")


def test_supplier_layout_is_sanitized() -> None:
    key = supplier_source_object_key(
        supplier_id="SUP-BEVCO",
        document_id="42",
        filename="../secret.csv",
    )
    assert key == "supplier-documents/SUP-BEVCO/42/source/secret.csv"
    assert is_safe_object_key(key)
    with pytest.raises(StorageError):
        supplier_source_object_key(
            supplier_id="../x",
            document_id="1",
            filename="a.csv",
        )
