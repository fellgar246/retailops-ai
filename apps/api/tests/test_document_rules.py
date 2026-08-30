from decimal import Decimal

from retailops_api.documents.rules import (
    CASE_PACK_NOT_POSITIVE,
    COST_NEGATIVE,
    DUPLICATE_EAN,
    DUPLICATE_SUPPLIER_SKU,
    INVALID_EAN,
    INVALID_VAT,
    LEAD_TIME_NEGATIVE,
    MOQ_NEGATIVE,
    REQUIRED_FIELD,
    rule_case_pack_positive,
    rule_cost_non_negative,
    rule_duplicate_ean,
    rule_duplicate_supplier_sku,
    rule_ean_format,
    rule_lead_time_non_negative,
    rule_moq_non_negative,
    rule_required_fields,
    rule_vat_allowed,
    validate_sheet,
)
from retailops_api.documents.types import RuleConfig, SupplierSheetRow


def _row(**overrides: object) -> SupplierSheetRow:
    values: dict[str, object] = {
        "row_number": 2,
        "supplier_sku": "NW-1",
        "ean": "7501999000011",
        "description": "Item",
        "category": "BEV-SOFT",
        "cost": Decimal("1.0000"),
        "vat": Decimal("16"),
        "case_pack": 12,
        "minimum_order_quantity": 1,
        "lead_time_days": 3,
    }
    values.update(overrides)
    return SupplierSheetRow(**values)  # type: ignore[arg-type]


def test_required_fields_skip_cells_that_failed_to_parse() -> None:
    row = _row(cost=None, invalid_fields=frozenset({"cost"}))

    codes = [item.code for item in rule_required_fields(row, RuleConfig())]

    assert REQUIRED_FIELD not in codes


def test_required_fields_flag_a_blank_description() -> None:
    findings = rule_required_fields(_row(description=None), RuleConfig())

    assert findings[0].code == REQUIRED_FIELD
    assert findings[0].field == "description"


def test_ean_must_be_8_to_14_digits() -> None:
    assert rule_ean_format(_row(ean="7501999000011")) == []
    finding = rule_ean_format(_row(ean="ABC"))[0]
    assert finding.code == INVALID_EAN


def test_numeric_bounds() -> None:
    assert rule_cost_non_negative(_row(cost=Decimal("-0.01")))[0].code == COST_NEGATIVE
    assert rule_case_pack_positive(_row(case_pack=0))[0].code == CASE_PACK_NOT_POSITIVE
    assert rule_moq_non_negative(_row(minimum_order_quantity=-1))[0].code == MOQ_NEGATIVE
    assert rule_lead_time_non_negative(_row(lead_time_days=-1))[0].code == LEAD_TIME_NEGATIVE


def test_vat_must_be_a_configured_rate() -> None:
    config = RuleConfig(allowed_vat=(Decimal("0"), Decimal("8"), Decimal("16")))

    assert rule_vat_allowed(_row(vat=Decimal("16")), config) == []
    assert rule_vat_allowed(_row(vat=Decimal("12")), config)[0].code == INVALID_VAT


def test_duplicate_supplier_sku_and_ean() -> None:
    first = _row(row_number=2, supplier_sku="NW-1", ean="7501999000011")
    second = _row(row_number=3, supplier_sku="NW-1", ean="7501999000011")

    sku_findings = rule_duplicate_supplier_sku((first, second))
    ean_findings = rule_duplicate_ean((first, second))

    assert {item.code for item in sku_findings} == {DUPLICATE_SUPPLIER_SKU}
    assert {item.row_number for item in sku_findings} == {2, 3}
    assert {item.code for item in ean_findings} == {DUPLICATE_EAN}


def test_a_clean_row_has_no_sheet_findings() -> None:
    assert validate_sheet((_row(),)) == []
