"""Cloud-neutral document store and a local filesystem implementation.

Operations:

- save bytes and receive a generated key
- read / open
- exists
- metadata (size, checksum, original filename, media type)
- controlled deletion

``LocalDocumentStorage`` writes under a configured root. Keys are generated
hex identifiers; the original filename is never used as a path component.
The same operations map onto an object store (put, get, head, delete) without
changing callers.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Protocol
from uuid import uuid4

from retailops_api.documents.types import StorageError

KEY_PATTERN = re.compile(r"^[0-9a-f]{32}$")
CHECKSUM_ALGORITHM = "sha256"
META_SUFFIX = ".meta.json"


@dataclass(frozen=True)
class StoredObject:
    key: str
    checksum: str
    size: int
    media_type: str
    filename: str


@dataclass(frozen=True)
class ObjectMetadata:
    key: str
    checksum: str
    size: int
    media_type: str | None = None
    filename: str | None = None


class DocumentStorage(Protocol):
    """Bytes in, generated key out. Implementations must not assume a cloud."""

    def save(self, data: bytes, *, filename: str, media_type: str) -> StoredObject: ...

    def read(self, key: str) -> bytes: ...

    def open(self, key: str) -> BinaryIO: ...

    def exists(self, key: str) -> bool: ...

    def metadata(self, key: str) -> ObjectMetadata: ...

    def delete(self, key: str) -> None: ...


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_filename(name: str) -> str:
    """Keep the basename only. The result is never used as a storage path."""
    base = Path(name).name.replace("\x00", "")
    if base in {"", ".", ".."}:
        return "document"
    return base[:255]


class LocalDocumentStorage:
    """Filesystem objects: ``<root>/<32-hex-key>`` plus a JSON sidecar."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, data: bytes, *, filename: str, media_type: str) -> StoredObject:
        key = self._unused_key()
        path = self._resolve(key)
        path.write_bytes(data)
        stored = StoredObject(
            key=key,
            checksum=sha256_hex(data),
            size=len(data),
            media_type=media_type,
            filename=safe_filename(filename),
        )
        self._write_sidecar(stored)
        return stored

    def read(self, key: str) -> bytes:
        return self._object_path(key).read_bytes()

    def open(self, key: str) -> BinaryIO:
        return self._object_path(key).open("rb")

    def exists(self, key: str) -> bool:
        return self._resolve(key).is_file()

    def metadata(self, key: str) -> ObjectMetadata:
        path = self._object_path(key)
        sidecar = self._sidecar_path(key)
        size = path.stat().st_size
        checksum = sha256_hex(path.read_bytes())
        media_type: str | None = None
        filename: str | None = None
        if sidecar.is_file():
            payload = json.loads(sidecar.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                media_type = str(payload["media_type"]) if payload.get("media_type") else None
                filename = str(payload["filename"]) if payload.get("filename") else None
                recorded = payload.get("checksum")
                if isinstance(recorded, str) and recorded:
                    checksum = recorded
        return ObjectMetadata(
            key=key,
            checksum=checksum,
            size=size,
            media_type=media_type,
            filename=filename,
        )

    def delete(self, key: str) -> None:
        path = self._object_path(key)
        sidecar = self._sidecar_path(key)
        path.unlink()
        if sidecar.is_file():
            sidecar.unlink()

    def _unused_key(self) -> str:
        for _ in range(8):
            key = uuid4().hex
            if not self._resolve(key).exists():
                return key
        raise StorageError("could not allocate a unique storage key")

    def _object_path(self, key: str) -> Path:
        path = self._resolve(key)
        if not path.is_file():
            raise StorageError(f"unknown storage key {key!r}")
        return path

    def _sidecar_path(self, key: str) -> Path:
        return self._resolve(key).with_name(f"{key}{META_SUFFIX}")

    def _write_sidecar(self, stored: StoredObject) -> None:
        payload = {
            "filename": stored.filename,
            "media_type": stored.media_type,
            "checksum": stored.checksum,
            "size": stored.size,
            "algorithm": CHECKSUM_ALGORITHM,
        }
        self._sidecar_path(stored.key).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _resolve(self, key: str) -> Path:
        if not KEY_PATTERN.fullmatch(key):
            raise StorageError(f"invalid storage key {key!r}")
        root = self.root.resolve()
        path = (root / key).resolve()
        if path.parent != root:
            raise StorageError(f"storage key escapes the configured root: {key!r}")
        return path
