"""Dataset validation names the table, row and field that failed."""

from datetime import date
from decimal import Decimal

import pytest

from retailops_api.dataset.contract import (
    Catalog,
    CategoryRow,
    Dataset,
    ProductRow,
    SalesRow,
    StoreRow,
    SupplierProductRow,
    SupplierRow,
)
from retailops_api.dataset.validate import DatasetValidationError, assert_valid, validate_dataset
from retailops_api.db.seed import reference_catalog
from retailops_api.synthetic.config import GeneratorConfig
from retailops_api.synthetic.generate import generate_dataset


def test_a_generated_tiny_dataset_is_valid() -> None:
    dataset = generate_dataset(GeneratorConfig.from_preset("tiny"))

    assert validate_dataset(dataset) == []
    assert_valid(dataset)


def test_the_development_reference_catalog_is_valid() -> None:
    from retailops_api.dataset.validate import validate_catalog

    assert validate_catalog(reference_catalog()) == []


def test_a_duplicate_sku_is_reported_with_the_natural_key() -> None:
    dataset = generate_dataset(GeneratorConfig.from_preset("tiny"))
    catalog = dataset.catalog
    duplicate = catalog.products[0]
    broken = Dataset(
        catalog=Catalog(
            categories=catalog.categories,
            products=(*catalog.products, duplicate),
            suppliers=catalog.suppliers,
            supplier_products=catalog.supplier_products,
            stores=catalog.stores,
        ),
        sales=dataset.sales,
        calendar=dataset.calendar,
    )

    issues = validate_dataset(broken)
    codes = {issue.code for issue in issues}
    assert "duplicate_key" in codes
    sku_issues = [issue for issue in issues if issue.natural_key == duplicate.sku]
    assert sku_issues
    assert "sku" in sku_issues[0].message


def test_a_broken_category_reference_names_the_product() -> None:
    dataset = generate_dataset(GeneratorConfig.from_preset("tiny"))
    product = dataset.catalog.products[0]
    replaced = product.__class__(
        sku=product.sku,
        name=product.name,
        category_code="NO-SUCH",
        ean=product.ean,
        description=product.description,
        active=product.active,
    )
    catalog = dataset.catalog
    broken = Dataset(
        catalog=Catalog(
            categories=catalog.categories,
            products=(replaced, *catalog.products[1:]),
            suppliers=catalog.suppliers,
            supplier_products=catalog.supplier_products,
            stores=catalog.stores,
        ),
        sales=(),
        calendar=dataset.calendar,
    )

    issues = validate_dataset(broken)
    match = next(issue for issue in issues if issue.field == "category_code")
    assert match.code == "broken_reference"
    assert product.sku in (match.natural_key or "")
    assert "NO-SUCH" in match.message


def test_negative_units_are_rejected() -> None:
    dataset = generate_dataset(GeneratorConfig.from_preset("tiny"))
    row = dataset.sales[0]
    bad = SalesRow(
        store_code=row.store_code,
        product_sku=row.product_sku,
        business_date=row.business_date,
        units_sold=-3,
        unit_price=row.unit_price,
        discount_amount=row.discount_amount,
        promotion=row.promotion,
        stock_on_hand=row.stock_on_hand,
    )
    broken = Dataset(
        catalog=dataset.catalog,
        sales=(bad, *dataset.sales[1:]),
        calendar=dataset.calendar,
    )

    issues = validate_dataset(broken)
    match = next(issue for issue in issues if issue.field == "units_sold")
    assert match.code == "negative_value"
    assert match.table == "daily_sales"


def test_an_invalid_identifier_mentions_the_expected_shape() -> None:
    catalog = Catalog(
        categories=(CategoryRow("not-a-code", "X"),),
        products=(ProductRow("SKU-0001", "P", "not-a-code"),),
        suppliers=(SupplierRow("SUP-001", "S"),),
        supplier_products=(SupplierProductRow("SUP-001", "SKU-0001", Decimal("1.0000"), 6, 1, 2),),
        stores=(StoreRow("ST-001", "Store", "Central", "express"),),
    )
    issues = validate_dataset(Dataset(catalog=catalog, sales=(), calendar=()))

    category_issue = next(issue for issue in issues if issue.table == "categories")
    assert category_issue.code == "invalid_identifier"
    assert "A-Z" in category_issue.message


def test_assert_valid_raises_a_readable_error() -> None:
    catalog = Catalog(
        categories=(CategoryRow("BEV", ""),),
        products=(),
        suppliers=(),
        supplier_products=(),
        stores=(),
    )

    with pytest.raises(DatasetValidationError, match="categories") as caught:
        assert_valid(Dataset(catalog=catalog, sales=(), calendar=()))

    assert "name is required" in str(caught.value)


def test_a_sale_on_an_unknown_date_is_flagged() -> None:
    dataset = generate_dataset(GeneratorConfig.from_preset("tiny"))
    row = dataset.sales[0]
    stray = SalesRow(
        store_code=row.store_code,
        product_sku=row.product_sku,
        business_date=date(1999, 1, 1),
        units_sold=1,
        unit_price=row.unit_price,
        discount_amount=row.discount_amount,
        promotion=False,
        stock_on_hand=1,
    )
    issues = validate_dataset(
        Dataset(catalog=dataset.catalog, sales=(stray,), calendar=dataset.calendar)
    )

    assert any(issue.code == "invalid_date" for issue in issues)
