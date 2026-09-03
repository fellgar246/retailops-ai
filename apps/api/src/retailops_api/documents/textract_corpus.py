"""Versioned synthetic Textract evaluation corpus.

Cases are generated in-process. Expected values come from the same builders
as the local document fixtures. No confidential documents or raw AWS
responses are stored.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from retailops_api.documents.corpus import (
    MALFORMED_ROW_ROWS,
    MISSING_FIELD_ROWS,
    VALID_ROWS,
    csv_bytes,
    pdf_bytes,
)
from retailops_api.documents.pdf import write_text_pdf
from retailops_api.documents.schema import SHEET_COLUMNS
from retailops_api.documents.textract import textract_response_to_parse_result
from retailops_api.documents.types import ParseResult, SupplierSheetRow

CORPUS_VERSION = "v001"

CANONICAL_FIELDS = (
    "supplier_sku",
    "ean",
    "description",
    "category",
    "cost",
    "vat",
    "case_pack",
    "minimum_order_quantity",
    "lead_time_days",
)
NUMERIC_FIELDS = ("cost", "vat", "case_pack", "minimum_order_quantity", "lead_time_days")


@dataclass(frozen=True)
class CorpusCase:
    case_id: str
    description: str
    rows: tuple[tuple[str, ...], ...]
    media: str
    expected_issues: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExtractionScore:
    case_id: str
    field_presence: float
    normalized_exact_match: float
    row_recovery: float
    ean_recovery: float
    numeric_value_recovery: float

    def to_dict(self) -> dict[str, float | str]:
        return {
            "case_id": self.case_id,
            "field_presence": round(self.field_presence, 4),
            "normalized_exact_match": round(self.normalized_exact_match, 4),
            "row_recovery": round(self.row_recovery, 4),
            "ean_recovery": round(self.ean_recovery, 4),
            "numeric_value_recovery": round(self.numeric_value_recovery, 4),
        }


CORPUS_CASES: tuple[CorpusCase, ...] = (
    CorpusCase("clean", "Clean supplier PDF", VALID_ROWS[:1], "pdf"),
    CorpusCase("noisy", "Noisy supplier PDF with chrome", VALID_ROWS[:1], "noisy-pdf"),
    CorpusCase("scanned", "Scanned/image-style table", VALID_ROWS[:1], "image-pdf"),
    CorpusCase("multi_row", "Multi-row table", VALID_ROWS, "pdf"),
    CorpusCase("missing_field", "Missing description", MISSING_FIELD_ROWS, "pdf"),
    CorpusCase("ambiguous", "Malformed numeric cost", MALFORMED_ROW_ROWS, "pdf"),
)


def corpus_cases() -> tuple[CorpusCase, ...]:
    return CORPUS_CASES


def case_bytes(case: CorpusCase) -> bytes:
    if case.media == "noisy-pdf":
        return _noisy_pdf(case.rows)
    if case.media == "image-pdf":
        return image_only_pdf()
    return pdf_bytes(case.rows)


def expected_rows(case: CorpusCase) -> tuple[tuple[str, ...], ...]:
    return case.rows


def synthetic_textract_table(
    rows: Sequence[Sequence[str]],
    *,
    headers: Sequence[str] = SHEET_COLUMNS,
    page: int = 1,
    confidence: float = 99.0,
    missing_cells: frozenset[tuple[int, int]] = frozenset(),
) -> dict[str, Any]:
    """Hand-built AnalyzeDocument JSON. Not a captured AWS payload."""

    blocks: list[dict[str, Any]] = []
    table_id = "table-1"
    cell_ids: list[str] = []
    grid = [list(headers), *[list(row) for row in rows]]
    for row_index, row in enumerate(grid, start=1):
        for col_index, value in enumerate(row, start=1):
            cell_id = f"cell-{row_index}-{col_index}"
            cell_ids.append(cell_id)
            text = "" if (row_index - 2, col_index - 1) in missing_cells else str(value)
            word_id = f"word-{row_index}-{col_index}"
            blocks.append(
                {
                    "Id": word_id,
                    "BlockType": "WORD",
                    "Text": text,
                    "Confidence": confidence,
                    "Page": page,
                }
            )
            blocks.append(
                {
                    "Id": cell_id,
                    "BlockType": "CELL",
                    "RowIndex": row_index,
                    "ColumnIndex": col_index,
                    "Confidence": confidence,
                    "Page": page,
                    "Relationships": [{"Type": "CHILD", "Ids": [word_id]}],
                }
            )
    blocks.insert(
        0,
        {
            "Id": table_id,
            "BlockType": "TABLE",
            "Page": page,
            "Confidence": confidence,
            "Relationships": [{"Type": "CHILD", "Ids": cell_ids}],
        },
    )
    return {"Blocks": blocks, "DocumentMetadata": {"Pages": page}}


def score_extraction(case: CorpusCase, parsed: ParseResult) -> ExtractionScore:
    expected = [_row_map(row) for row in case.rows]
    observed = [_observed_map(row) for row in parsed.rows]
    paired = list(zip(expected, observed, strict=False))
    field_total = 0
    field_present = 0
    exact = 0
    exact_total = 0
    ean_ok = 0
    ean_total = 0
    numeric_ok = 0
    numeric_total = 0
    for exp, obs in paired:
        for name in CANONICAL_FIELDS:
            wanted = exp.get(name)
            got = obs.get(name)
            if wanted:
                field_total += 1
                if got:
                    field_present += 1
                exact_total += 1
                if _normalized(wanted) == _normalized(got):
                    exact += 1
            if name == "ean" and wanted:
                ean_total += 1
                if _normalized(wanted) == _normalized(got):
                    ean_ok += 1
            if name in NUMERIC_FIELDS and wanted:
                numeric_total += 1
                if _normalized(wanted) == _normalized(got):
                    numeric_ok += 1
    return ExtractionScore(
        case_id=case.case_id,
        field_presence=_ratio(field_present, field_total),
        normalized_exact_match=_ratio(exact, exact_total),
        row_recovery=_ratio(len(paired), len(expected)),
        ean_recovery=_ratio(ean_ok, ean_total),
        numeric_value_recovery=_ratio(numeric_ok, numeric_total),
    )


def evaluate_corpus(
    payloads: dict[str, dict[str, Any]] | None = None,
) -> tuple[ExtractionScore, ...]:
    scores: list[ExtractionScore] = []
    for case in CORPUS_CASES:
        payload = (payloads or {}).get(case.case_id) or synthetic_textract_table(case.rows)
        parsed = textract_response_to_parse_result(payload)
        scores.append(score_extraction(case, parsed))
    return tuple(scores)


def image_only_pdf() -> bytes:
    """Single-page PDF with an inline image and no extractable text."""

    image = (
        b"\x00\xff\x00\xff\xff\x00\xff\x00"
        b"\xff\x00\xff\x00\x00\xff\x00\xff"
        b"\x00\xff\x00\xff\xff\x00\xff\x00"
        b"\xff\x00\xff\x00\x00\xff\x00\xff"
    )
    content = b"q\n8 0 0 8 40 700 cm\n/Im1 Do\nQ\n"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Contents 4 0 R /Resources << /XObject << /Im1 5 0 R >> >> >>"
        ),
        b"<< /Length "
        + str(len(content)).encode("ascii")
        + b" >>\nstream\n"
        + content
        + b"\nendstream",
        (
            b"<< /Type /XObject /Subtype /Image /Width 8 /Height 4 "
            b"/ColorSpace /DeviceGray /BitsPerComponent 8 /Length "
            + str(len(image)).encode("ascii")
            + b" >>\nstream\n"
            + image
            + b"\nendstream"
        ),
    ]
    parts = [b"%PDF-1.4\n"]
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(sum(len(part) for part in parts))
        parts.append(f"{number} 0 obj\n".encode("ascii") + body + b"\nendobj\n")
    xref_at = sum(len(part) for part in parts)
    xref = [b"xref\n", f"0 {len(objects) + 1}\n".encode("ascii"), b"0000000000 65535 f \n"]
    for offset in offsets[1:]:
        xref.append(f"{offset:010d} 00000 n \n".encode("ascii"))
    trailer = (
        b"trailer\n<< /Size "
        + str(len(objects) + 1).encode("ascii")
        + b" /Root 1 0 R >>\nstartxref\n"
        + str(xref_at).encode("ascii")
        + b"\n%%EOF\n"
    )
    return b"".join(parts) + b"".join(xref) + trailer


def _noisy_pdf(rows: Sequence[Sequence[str]]) -> bytes:
    header = ",".join(SHEET_COLUMNS)
    body = "\n".join(",".join(row) for row in rows)
    text = (
        "CONFIDENTIAL DRAFT — ignore this banner\n"
        "Supplier offer 2026 / page chrome / fax header\n\n"
        f"{header}\n"
        f"{body}\n"
        "Footer: totals are not part of the sheet\n"
    )
    return write_text_pdf(text)


def _row_map(row: Sequence[str]) -> dict[str, str]:
    return {
        name: str(row[index]).strip() if index < len(row) else ""
        for index, name in enumerate(SHEET_COLUMNS)
    }


def _observed_map(row: SupplierSheetRow) -> dict[str, str]:
    return {
        "supplier_sku": row.supplier_sku or "",
        "ean": row.ean or "",
        "description": row.description or "",
        "category": row.category or "",
        "cost": _decimal_text(row.cost),
        "vat": _decimal_text(row.vat),
        "case_pack": "" if row.case_pack is None else str(row.case_pack),
        "minimum_order_quantity": (
            "" if row.minimum_order_quantity is None else str(row.minimum_order_quantity)
        ),
        "lead_time_days": "" if row.lead_time_days is None else str(row.lead_time_days),
    }


def _decimal_text(value: Decimal | None) -> str:
    if value is None:
        return ""
    text = format(value, "f")
    if "." not in text:
        return text
    return text.rstrip("0").rstrip(".")


def _normalized(value: str | None) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    try:
        number = Decimal(text)
        return format(number.normalize(), "f").rstrip("0").rstrip(".") or "0"
    except Exception:
        return text.casefold()


def _ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def csv_bytes_for_case(case: CorpusCase) -> bytes:
    return csv_bytes(case.rows)
