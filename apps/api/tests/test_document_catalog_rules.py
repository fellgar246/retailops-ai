from decimal import Decimal

from retailops_api.documents.catalog import CatalogIndex, ProductRef, TermRef
from retailops_api.documents.catalog_rules import (
    CATEGORY_MISMATCH,
    COST_INCREASE,
    EAN_MATCHES_EXISTING,
    SUPPLIER_SKU_MAPPED_ELSEWHERE,
    rule_category_mismatch,
    rule_cost_increase,
    rule_ean_matches_existing,
    rule_supplier_sku_mapped_elsewhere,
)
from retailops_api.documents.types import SupplierSheetRow

COLA = ProductRef(
    id=1,
    sku="SKU-1001",
    ean="7501000110018",
    name="Cola Classic 355ml Can",
    category_code="BEV-SOFT",
    category_name="Soft Drinks",
)
WATER = ProductRef(
    id=2,
    sku="SKU-1004",
    ean="7501000110049",
    name="Still Water 1L Bottle",
    category_code="BEV-WATER",
    category_name="Water",
)


def _index() -> CatalogIndex:
    bevco = TermRef(
        supplier_id=10,
        supplier_code="SUP-BEVCO",
        supplier_sku="BC-COLA-355",
        cost=Decimal("7.4500"),
        product=COLA,
    )
    natgro = TermRef(
        supplier_id=20,
        supplier_code="SUP-NATGRO",
        supplier_sku="BC-COLA-355",
        cost=Decimal("7.9900"),
        product=COLA,
    )
    water = TermRef(
        supplier_id=10,
        supplier_code="SUP-BEVCO",
        supplier_sku="BC-WATER-1L",
        cost=Decimal("5.2500"),
        product=WATER,
    )
    return CatalogIndex(
        products_by_ean={COLA.ean: COLA, WATER.ean: WATER},  # type: ignore[dict-item]
        terms_by_supplier_sku={"BC-COLA-355": (bevco, natgro), "BC-WATER-1L": (water,)},
        terms_by_supplier_ean={(10, COLA.ean): bevco, (10, WATER.ean): water},  # type: ignore[dict-item]
        terms_by_supplier_and_sku={(10, "BC-COLA-355"): bevco, (10, "BC-WATER-1L"): water},
    )


def _row(**overrides: object) -> SupplierSheetRow:
    values: dict[str, object] = {
        "row_number": 2,
        "supplier_sku": "BC-COLA-355",
        "ean": "7501000110018",
        "description": "Cola Classic 355ml Can",
        "category": "BEV-SOFT",
        "cost": Decimal("7.4500"),
    }
    values.update(overrides)
    return SupplierSheetRow(**values)  # type: ignore[arg-type]


def test_ean_match_is_informational() -> None:
    findings = rule_ean_matches_existing(_row(), _index())

    assert findings[0].code == EAN_MATCHES_EXISTING
    assert findings[0].proposed_value == "SKU-1001"


def test_supplier_sku_used_by_another_vendor() -> None:
    findings = rule_supplier_sku_mapped_elsewhere(_row(), _index(), supplier_id=10)

    elsewhere = [item for item in findings if "SUP-NATGRO" in item.message]
    assert elsewhere[0].code == SUPPLIER_SKU_MAPPED_ELSEWHERE


def test_supplier_sku_bound_to_a_different_product() -> None:
    row = _row(ean="7501999000999")
    findings = rule_supplier_sku_mapped_elsewhere(row, _index(), supplier_id=10)

    assert any(item.code == SUPPLIER_SKU_MAPPED_ELSEWHERE for item in findings)
    assert any("SKU-1001" in item.message for item in findings)


def test_cost_increase_against_current_term() -> None:
    findings = rule_cost_increase(_row(cost=Decimal("9.0000")), _index(), supplier_id=10)

    assert findings[0].code == COST_INCREASE
    assert findings[0].proposed_value == "7.4500"


def test_equal_cost_is_not_an_increase() -> None:
    assert rule_cost_increase(_row(cost=Decimal("7.4500")), _index(), supplier_id=10) == []


def test_category_mismatch_against_the_known_product() -> None:
    findings = rule_category_mismatch(_row(category="HOME-CLEAN"), _index())

    assert findings[0].code == CATEGORY_MISMATCH
    assert findings[0].proposed_value == "BEV-SOFT"


def test_category_name_is_accepted() -> None:
    assert rule_category_mismatch(_row(category="Soft Drinks"), _index()) == []
