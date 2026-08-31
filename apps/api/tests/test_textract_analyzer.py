import json
from decimal import Decimal
from pathlib import Path

import pytest

from retailops_api.core.aws import AwsAdapterError
from retailops_api.documents.textract import (
    TextractDocumentAnalyzer,
    textract_response_to_parse_result,
)
from retailops_api.documents.types import ParseError
from tests.aws_fakes import FakeTextract

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "textract"


def test_textract_table_fixture_becomes_a_canonical_sheet() -> None:
    payload = json.loads((FIXTURES / "supplier_sheet_table.json").read_text(encoding="utf-8"))
    result = TextractDocumentAnalyzer().analyze_response(payload)

    assert len(result.rows) == 1
    row = result.rows[0]
    assert row.supplier_sku == "NW-SODA-330"
    assert row.ean == "7501999000011"
    assert row.description == "New Cola 330ml"
    assert row.category == "BEV-SOFT"
    assert row.cost == Decimal("6.5000")
    assert row.vat == Decimal("16")
    assert row.case_pack == 24
    assert row.minimum_order_quantity == 1
    assert row.lead_time_days == 5


def test_textract_line_fixture_parses_delimited_text() -> None:
    payload = json.loads((FIXTURES / "supplier_sheet_lines.json").read_text(encoding="utf-8"))
    result = textract_response_to_parse_result(payload)

    assert len(result.rows) == 1
    assert result.rows[0].supplier_sku == "NW-WATER-500"
    assert result.rows[0].category == "BEV-WATER"


def test_textract_empty_response_is_a_parse_error() -> None:
    with pytest.raises(ParseError, match="no blocks"):
        textract_response_to_parse_result({"Blocks": []})


def test_textract_analyze_uses_injected_client() -> None:
    payload = json.loads((FIXTURES / "supplier_sheet_table.json").read_text(encoding="utf-8"))
    client = FakeTextract(payload)
    analyzer = TextractDocumentAnalyzer(client)
    result = analyzer.analyze(b"%PDF-fixture", media_type="application/pdf", filename="offer.pdf")

    assert client.calls
    assert result.rows[0].supplier_sku == "NW-SODA-330"


def test_textract_analyze_without_client_is_an_error() -> None:
    with pytest.raises(AwsAdapterError, match="not configured"):
        TextractDocumentAnalyzer().analyze(b"bytes")
