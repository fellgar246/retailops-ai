"""Builders for the supplier-sheet fixtures used by processing tests.

CSV text is the source of truth. XLSX and text-PDF bytes are derived from the
same rows so every format exercises the same cases.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Sequence
from pathlib import Path

from retailops_api.documents.pdf import write_text_pdf
from retailops_api.documents.schema import SHEET_COLUMNS

VALID_ROWS: tuple[tuple[str, ...], ...] = (
    (
        "NW-SODA-330",
        "7501999000011",
        "New Cola 330ml",
        "BEV-SOFT",
        "6.5000",
        "16",
        "24",
        "1",
        "5",
    ),
    (
        "NW-WATER-500",
        "7501999000028",
        "Spring Water 500ml",
        "BEV-WATER",
        "4.2000",
        "16",
        "12",
        "1",
        "4",
    ),
)

INVALID_EAN_ROWS: tuple[tuple[str, ...], ...] = (
    (
        "NW-SODA-330",
        "NOT-AN-EAN",
        "New Cola 330ml",
        "BEV-SOFT",
        "6.5000",
        "16",
        "24",
        "1",
        "5",
    ),
)

MISSING_FIELD_ROWS: tuple[tuple[str, ...], ...] = (
    (
        "NW-SODA-330",
        "7501999000011",
        "",
        "BEV-SOFT",
        "6.5000",
        "16",
        "24",
        "1",
        "5",
    ),
)

DUPLICATE_SKU_ROWS: tuple[tuple[str, ...], ...] = (
    (
        "NW-SODA-330",
        "7501999000011",
        "New Cola 330ml",
        "BEV-SOFT",
        "6.5000",
        "16",
        "24",
        "1",
        "5",
    ),
    (
        "NW-SODA-330",
        "7501999000035",
        "New Cola Zero 330ml",
        "BEV-SOFT",
        "6.5000",
        "16",
        "24",
        "1",
        "5",
    ),
)

COST_INCREASE_ROWS: tuple[tuple[str, ...], ...] = (
    (
        "BC-COLA-355",
        "7501000110018",
        "Cola Classic 355ml Can",
        "BEV-SOFT",
        "9.0000",
        "16",
        "24",
        "2",
        "3",
    ),
)

INVALID_VAT_ROWS: tuple[tuple[str, ...], ...] = (
    (
        "NW-SODA-330",
        "7501999000011",
        "New Cola 330ml",
        "BEV-SOFT",
        "6.5000",
        "12",
        "24",
        "1",
        "5",
    ),
)

MALFORMED_ROW_ROWS: tuple[tuple[str, ...], ...] = (
    (
        "NW-SODA-330",
        "7501999000011",
        "New Cola 330ml",
        "BEV-SOFT",
        "not-a-price",
        "16",
        "24",
        "1",
        "5",
    ),
)


def csv_bytes(rows: Sequence[Sequence[str]], *, headers: Sequence[str] = SHEET_COLUMNS) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def xlsx_bytes(rows: Sequence[Sequence[str]], *, headers: Sequence[str] = SHEET_COLUMNS) -> bytes:
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.append(list(headers))
    for row in rows:
        sheet.append(list(row))
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


def pdf_bytes(rows: Sequence[Sequence[str]], *, headers: Sequence[str] = SHEET_COLUMNS) -> bytes:
    return write_text_pdf(csv_bytes(rows, headers=headers).decode("utf-8"))


def write_csv(
    path: Path, rows: Sequence[Sequence[str]], *, headers: Sequence[str] = SHEET_COLUMNS
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(csv_bytes(rows, headers=headers))
    return path
