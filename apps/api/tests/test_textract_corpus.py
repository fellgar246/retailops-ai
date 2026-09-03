import pytest

from retailops_api.documents.textract import textract_response_to_parse_result
from retailops_api.documents.textract_corpus import (
    CORPUS_VERSION,
    corpus_cases,
    evaluate_corpus,
    image_only_pdf,
    score_extraction,
    synthetic_textract_table,
)


def test_corpus_has_the_six_required_cases() -> None:
    ids = [case.case_id for case in corpus_cases()]
    assert CORPUS_VERSION == "v001"
    assert ids == [
        "clean",
        "noisy",
        "scanned",
        "multi_row",
        "missing_field",
        "ambiguous",
    ]


def test_synthetic_table_recovers_rows_and_confidence() -> None:
    case = corpus_cases()[0]
    payload = synthetic_textract_table(case.rows, page=2, confidence=91.0)
    parsed = textract_response_to_parse_result(payload)
    assert parsed.extraction is not None
    assert parsed.extraction.analyzer == "textract"
    assert parsed.extraction.page_count == 2
    assert parsed.extraction.table_count == 1
    assert parsed.extraction.min_confidence == 91.0
    assert parsed.rows[0].page == 2
    assert parsed.rows[0].confidence == pytest.approx(0.91)
    score = score_extraction(case, parsed)
    assert score.row_recovery == 1.0
    assert score.ean_recovery == 1.0
    assert score.field_presence == 1.0


def test_corpus_evaluation_is_deterministic() -> None:
    scores = {item.case_id: item for item in evaluate_corpus()}
    assert scores["clean"].normalized_exact_match == 1.0
    assert scores["multi_row"].row_recovery == 1.0
    assert scores["ambiguous"].numeric_value_recovery < 1.0


def test_image_only_pdf_has_no_text_layer() -> None:
    from retailops_api.documents.pdf import extract_pdf_text

    assert not extract_pdf_text(image_only_pdf()).strip()
