import pytest

from retailops_api.documents.corpus import VALID_ROWS, pdf_bytes
from retailops_api.documents.pdf import parse_text_pdf, write_text_pdf
from retailops_api.documents.types import ParseError


def test_text_pdf_with_a_delimited_header_parses_like_csv() -> None:
    result = parse_text_pdf(pdf_bytes(VALID_ROWS))

    assert [row.supplier_sku for row in result.rows] == ["NW-SODA-330", "NW-WATER-500"]
    assert result.rows[0].row_number >= 2


def test_pdf_without_a_tabular_header_does_not_guess_a_table() -> None:
    data = write_text_pdf("This is a scanned-looking letter.\nNo columns here.")

    with pytest.raises(ParseError, match="tabular header"):
        parse_text_pdf(data)


def test_empty_text_pdf_is_rejected() -> None:
    data = write_text_pdf("   \n")

    with pytest.raises(ParseError, match="extractable text"):
        parse_text_pdf(data)
