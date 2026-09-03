"""Deterministic S3 object-key helpers for supplier documents.

The database ``storage_key`` stays a 32-hex identifier (64-character column).
The object key is reconstructed from that identifier plus a prefix:

    {prefix}/{storage-key}/source/payload

Original filenames live in object metadata, not in the key. Supplier and
document ids stay in the database. Callers that want the documented
hierarchical layout can build it with ``supplier_source_object_key``; the
storage adapter does not need those ids to read an object back.
"""

from __future__ import annotations

import re

from retailops_api.core.limits import DEFAULT_DOCUMENTS_PREFIX, LIVE_SMOKE_PREFIX
from retailops_api.documents.storage import KEY_PATTERN, safe_filename
from retailops_api.documents.types import StorageError

SOURCE_LEAF = "payload"
SOURCE_SEGMENT = "source"

_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$")
_UNSAFE = ("..", "/", "\\", "\x00")


def normalize_prefix(prefix: str) -> str:
    cleaned = prefix.strip().strip("/")
    if not cleaned:
        return ""
    for part in cleaned.split("/"):
        _require_segment(part, what="prefix segment")
    return cleaned


def validate_logical_key(key: str) -> str:
    if not KEY_PATTERN.fullmatch(key):
        raise StorageError(f"invalid storage key {key!r}")
    return key


def safe_object_leaf(name: str) -> str:
    leaf = safe_filename(name)
    if any(token in leaf for token in _UNSAFE) or leaf in {".", ".."}:
        raise StorageError(f"unsafe object leaf {name!r}")
    if "/" in leaf or "\\" in leaf:
        raise StorageError(f"object leaf must be a basename: {name!r}")
    return leaf


def source_object_key(
    logical_key: str,
    *,
    prefix: str = DEFAULT_DOCUMENTS_PREFIX,
    leaf: str = SOURCE_LEAF,
) -> str:
    """``{prefix}/{logical-key}/source/payload`` (or a sanitized leaf)."""

    key = validate_logical_key(logical_key)
    normalized = normalize_prefix(prefix)
    safe_leaf = safe_object_leaf(leaf)
    tail = f"{key}/{SOURCE_SEGMENT}/{safe_leaf}"
    return f"{normalized}/{tail}" if normalized else tail


def legacy_object_key(logical_key: str, *, prefix: str) -> str:
    """Flat ``{prefix}/{logical-key}`` used by the first S3 adapter layout."""

    key = validate_logical_key(logical_key)
    normalized = normalize_prefix(prefix)
    return f"{normalized}/{key}" if normalized else key


def supplier_source_object_key(
    *,
    supplier_id: str,
    document_id: str,
    filename: str,
    prefix: str = DEFAULT_DOCUMENTS_PREFIX,
) -> str:
    """Optional layout: ``{prefix}/{supplier}/{document}/source/{filename}``."""

    normalized = normalize_prefix(prefix)
    supplier = _require_segment(supplier_id, what="supplier id")
    document = _require_segment(document_id, what="document id")
    leaf = safe_object_leaf(filename)
    tail = f"{supplier}/{document}/{SOURCE_SEGMENT}/{leaf}"
    return f"{normalized}/{tail}" if normalized else tail


def is_safe_object_key(key: str) -> bool:
    if not key or key.startswith("/") or any(token in key for token in ("..", "\\", "\x00")):
        return False
    try:
        for part in key.split("/"):
            if part == "":
                return False
            _require_segment(part, what="object key segment")
    except StorageError:
        return False
    return True


__all__ = [
    "DEFAULT_DOCUMENTS_PREFIX",
    "LIVE_SMOKE_PREFIX",
    "SOURCE_LEAF",
    "SOURCE_SEGMENT",
    "is_safe_object_key",
    "legacy_object_key",
    "normalize_prefix",
    "safe_object_leaf",
    "source_object_key",
    "supplier_source_object_key",
    "validate_logical_key",
]


def _require_segment(value: str, *, what: str) -> str:
    text = value.strip()
    if not text or any(token in text for token in _UNSAFE):
        raise StorageError(f"invalid {what} {value!r}")
    if not _SEGMENT.fullmatch(text):
        raise StorageError(f"invalid {what} {value!r}")
    return text
