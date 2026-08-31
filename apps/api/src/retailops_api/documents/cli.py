"""Ingest a supplier sheet and run deterministic validation.

    make documents file=path/to/sheet.csv supplier=SUP-BEVCO

Or, from ``apps/api``:

    uv run retailops-documents --file path/to/sheet.csv --supplier SUP-BEVCO
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from retailops_api.core.adapters import document_storage_for
from retailops_api.core.config import get_settings
from retailops_api.db.session import get_session_factory
from retailops_api.documents.process import process_document
from retailops_api.documents.storage import LocalDocumentStorage
from retailops_api.documents.types import DocumentProcessError, ProcessResult
from retailops_api.domain.models.document import FindingSeverity


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    path = Path(args.file)
    if not path.is_file():
        print(f"error: file not found: {path}", file=sys.stderr)
        return 1
    try:
        data = path.read_bytes()
        storage = (
            LocalDocumentStorage(args.storage)
            if args.storage is not None
            else document_storage_for(get_settings())
        )
        with get_session_factory()() as session:
            try:
                result = process_document(
                    session,
                    storage,
                    supplier_code=args.supplier,
                    filename=path.name,
                    data=data,
                    media_type=args.media_type,
                )
                session.commit()
            except Exception:
                session.rollback()
                raise
        _print_result(result)
        return 0
    except DocumentProcessError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="retailops-documents",
        description=(
            "Store a supplier sheet, parse it, run deterministic validation "
            "against the live catalog and persist findings."
        ),
    )
    parser.add_argument("--file", required=True, type=Path, help="CSV, XLSX or text PDF.")
    parser.add_argument("--supplier", required=True, help="Supplier business code, e.g. SUP-BEVCO.")
    parser.add_argument(
        "--storage",
        type=Path,
        help="Local document root (default: <repo>/data/documents).",
    )
    parser.add_argument("--media-type", help="Override media-type detection from the filename.")
    return parser.parse_args(argv)


def _print_result(result: ProcessResult) -> None:
    counts = {severity.value: 0 for severity in FindingSeverity}
    for finding in result.findings:
        counts[finding.severity.value] += 1
    print(
        f"document={result.document_id}  supplier={result.supplier_code}  "
        f"status={result.status}  rows={result.row_count}  "
        f"findings={len(result.findings)}  "
        f"error={counts['error']} warning={counts['warning']} info={counts['info']}"
    )
    print(f"  storage_key={result.storage_key}  checksum={result.checksum}")
    for finding in result.findings:
        location = f"row {finding.row_number}" if finding.row_number else "document"
        field = f" {finding.field}" if finding.field else ""
        print(f"  {finding.severity.value} {finding.code} {location}{field}: {finding.message}")


if __name__ == "__main__":
    raise SystemExit(main())
