from decimal import Decimal
from pathlib import Path

import pytest

from retailops_api.documents.corpus import (
    MALFORMED_ROW_ROWS,
    VALID_ROWS,
    csv_bytes,
    xlsx_bytes,
)
from retailops_api.documents.parse import parse_csv, parse_supplier_sheet, parse_xlsx
from retailops_api.documents.schema import SHEET_COLUMNS
from retailops_api.documents.types import ParseError

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "supplier_documents"


def test_csv_normalises_aliased_headers_and_keeps_row_numbers() -> None:
    data = csv_bytes(
        VALID_ROWS,
        headers=(
            "Supplier SKU",
            "Barcode",
            "Product Name",
            "Category",
            "Unit Cost",
            "IVA",
            "Case Pack",
            "MOQ",
            "Lead Time",
        ),
    )
    result = parse_csv(data)

    assert len(result.rows) == 2
    first = result.rows[0]
    assert first.row_number == 2
    assert first.supplier_sku == "NW-SODA-330"
    assert first.ean == "7501999000011"
    assert first.cost == Decimal("6.5000")
    assert first.vat == Decimal("16")
    assert first.case_pack == 24
    assert first.minimum_order_quantity == 1
    assert first.lead_time_days == 5


def test_csv_fixture_is_the_canonical_valid_sheet() -> None:
    result = parse_csv((FIXTURES / "valid.csv").read_bytes())

    assert [row.supplier_sku for row in result.rows] == ["NW-SODA-330", "NW-WATER-500"]
    assert result.issues == ()


def test_blank_cells_become_none() -> None:
    result = parse_csv((FIXTURES / "missing_field.csv").read_bytes())

    assert result.rows[0].description is None
    assert result.issues == ()


def test_malformed_numeric_cell_is_an_actionable_issue() -> None:
    result = parse_csv(csv_bytes(MALFORMED_ROW_ROWS))

    assert result.rows[0].cost is None
    assert "cost" in result.rows[0].invalid_fields
    assert result.issues[0].code == "malformed_value"
    assert result.issues[0].row_number == 2
    assert result.issues[0].field == "cost"


def test_unrecognised_header_is_a_parse_error() -> None:
    with pytest.raises(ParseError, match="no recognised"):
        parse_csv(b"foo,bar\n1,2\n")


def test_xlsx_uses_excel_row_numbers() -> None:
    result = parse_xlsx(xlsx_bytes(VALID_ROWS, headers=SHEET_COLUMNS))

    assert [row.row_number for row in result.rows] == [2, 3]
    assert result.rows[1].supplier_sku == "NW-WATER-500"
    assert result.rows[1].minimum_order_quantity == 1


def test_empty_payload_is_a_parse_error() -> None:
    with pytest.raises(ParseError, match="empty"):
        parse_supplier_sheet(b"", media_type="text/csv")
