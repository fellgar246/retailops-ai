"""Catalog and sales ingestion: idempotency, rejects, metrics and reports."""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from retailops_api.dataset.contract import SalesRow
from retailops_api.domain.models import (
    Category,
    Product,
    SalesRecord,
    Store,
    Supplier,
    SupplierProduct,
)
from retailops_api.ingestion.catalog import CatalogIngestionError, ingest_catalog
from retailops_api.ingestion.report import IngestionRunReport
from retailops_api.ingestion.sales import ingest_sales
from retailops_api.synthetic.config import GeneratorConfig
from retailops_api.synthetic.generate import generate_dataset
from tests.conftest import requires_postgres


def _tiny(**overrides: object) -> GeneratorConfig:
    return GeneratorConfig.from_preset("tiny", **overrides)


def _count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def test_catalog_ingestion_writes_every_declared_row(session: Session) -> None:
    dataset = generate_dataset(_tiny())

    result = ingest_catalog(session, dataset.catalog)

    assert result.categories.created == len(dataset.catalog.categories)
    assert result.products.created == len(dataset.catalog.products)
    assert result.suppliers.created == len(dataset.catalog.suppliers)
    assert result.supplier_products.created == len(dataset.catalog.supplier_products)
    assert result.stores.created == len(dataset.catalog.stores)


def test_catalog_ingestion_is_idempotent(session: Session) -> None:
    dataset = generate_dataset(_tiny())
    ingest_catalog(session, dataset.catalog)
    session.commit()

    second = ingest_catalog(session, dataset.catalog)
    session.commit()

    assert second.created == 0
    assert second.updated == 0
    assert _count(session, Product) == len(dataset.catalog.products)


def test_a_broken_catalog_raises_and_the_caller_can_roll_back(session: Session) -> None:
    dataset = generate_dataset(_tiny())
    product = dataset.catalog.products[0]
    broken_product = product.__class__(
        sku=product.sku,
        name=product.name,
        category_code="MISSING",
        ean=product.ean,
        description=product.description,
        active=product.active,
    )
    catalog = dataset.catalog.__class__(
        categories=dataset.catalog.categories,
        products=(broken_product, *dataset.catalog.products[1:]),
        suppliers=dataset.catalog.suppliers,
        supplier_products=dataset.catalog.supplier_products,
        stores=dataset.catalog.stores,
    )

    with pytest.raises(CatalogIngestionError, match="MISSING"):
        ingest_catalog(session, catalog)
    session.rollback()

    assert _count(session, Category) == 0
    assert _count(session, Product) == 0


def test_sales_ingestion_writes_every_accepted_row(session: Session) -> None:
    dataset = generate_dataset(_tiny())
    ingest_catalog(session, dataset.catalog)

    stats = ingest_sales(session, dataset.sales)

    assert stats.rows_read == len(dataset.sales)
    assert stats.rows_accepted == len(dataset.sales)
    assert stats.rows_rejected == 0
    assert stats.duplicate_count == 0
    assert _count(session, SalesRecord) == len(dataset.sales)


def test_re_ingesting_sales_is_idempotent_and_counts_duplicates(session: Session) -> None:
    dataset = generate_dataset(_tiny())
    ingest_catalog(session, dataset.catalog)
    ingest_sales(session, dataset.sales)
    session.commit()

    again = ingest_sales(session, dataset.sales)
    session.commit()

    assert again.rows_accepted == len(dataset.sales)
    assert again.duplicate_count == len(dataset.sales)
    assert _count(session, SalesRecord) == len(dataset.sales)


def test_sales_ingestion_rejects_bad_rows_and_keeps_the_rest(session: Session) -> None:
    dataset = generate_dataset(_tiny())
    ingest_catalog(session, dataset.catalog)
    good = dataset.sales[0]
    bad_unknown = SalesRow(
        store_code="ST-999",
        product_sku=good.product_sku,
        business_date=good.business_date,
        units_sold=1,
        unit_price=good.unit_price,
        discount_amount=Decimal("0"),
        promotion=False,
        stock_on_hand=1,
    )
    bad_negative = SalesRow(
        store_code=good.store_code,
        product_sku=good.product_sku,
        business_date=date(2026, 6, 1),
        units_sold=-4,
        unit_price=good.unit_price,
        discount_amount=Decimal("0"),
        promotion=False,
        stock_on_hand=1,
    )

    stats = ingest_sales(session, (bad_unknown, bad_negative, good))

    assert stats.rows_read == 3
    assert stats.rows_accepted == 1
    assert stats.rows_rejected == 2
    assert {issue.code for issue in stats.validation_errors} == {
        "broken_reference",
        "negative_value",
    }
    assert _count(session, SalesRecord) == 1


def test_an_in_file_duplicate_is_rejected(session: Session) -> None:
    dataset = generate_dataset(_tiny())
    ingest_catalog(session, dataset.catalog)
    row = dataset.sales[0]
    twin = SalesRow(
        store_code=row.store_code,
        product_sku=row.product_sku,
        business_date=row.business_date,
        units_sold=99,
        unit_price=row.unit_price,
        discount_amount=row.discount_amount,
        promotion=row.promotion,
        stock_on_hand=row.stock_on_hand,
    )

    stats = ingest_sales(session, (row, twin))

    assert stats.rows_accepted == 1
    assert stats.rows_rejected == 1
    assert stats.validation_errors[0].code == "duplicate_key"


def test_the_run_report_carries_the_required_fields(session: Session) -> None:
    dataset = generate_dataset(_tiny())
    started = datetime(2026, 3, 1, tzinfo=UTC)
    catalog = ingest_catalog(session, dataset.catalog)
    sales = ingest_sales(session, dataset.sales)
    report = IngestionRunReport(
        source="synthetic:tiny",
        run_id="abc123",
        started_at=started,
        finished_at=datetime(2026, 3, 1, 0, 0, 1, tzinfo=UTC),
        rows_read=sales.rows_read,
        rows_accepted=sales.rows_accepted,
        rows_rejected=sales.rows_rejected,
        duplicate_count=sales.duplicate_count,
        validation_errors=sales.validation_errors,
        catalog=catalog,
        checksum="deadbeef",
    )

    payload = report.to_dict()
    assert payload["source"] == "synthetic:tiny"
    assert payload["run_id"] == "abc123"
    assert payload["rows_read"] == len(dataset.sales)
    assert payload["rows_accepted"] == len(dataset.sales)
    assert payload["rows_rejected"] == 0
    assert payload["duplicate_count"] == 0
    assert payload["validation_errors"] == []
    assert payload["checksum"] == "deadbeef"
    assert "categories" in payload["catalog"]
    assert "run_id" in report.format_text()
    assert "deadbeef" in report.to_json()


def test_generate_and_ingest_leaves_referential_integrity(session: Session) -> None:
    dataset = generate_dataset(_tiny())
    ingest_catalog(session, dataset.catalog)
    ingest_sales(session, dataset.sales)
    session.commit()

    assert _count(session, Category) == len(dataset.catalog.categories)
    assert _count(session, Product) == len(dataset.catalog.products)
    assert _count(session, Supplier) == len(dataset.catalog.suppliers)
    assert _count(session, SupplierProduct) == len(dataset.catalog.supplier_products)
    assert _count(session, Store) == len(dataset.catalog.stores)
    assert _count(session, SalesRecord) == len(dataset.sales)

    store_codes = set(session.scalars(select(Store.code)))
    product_skus = set(session.scalars(select(Product.sku)))
    for record in session.scalars(select(SalesRecord)):
        assert record.store.code in store_codes
        assert record.product.sku in product_skus


@requires_postgres
def test_generate_and_ingest_works_against_postgresql(postgres_session: Session) -> None:
    dataset = generate_dataset(_tiny())
    first = ingest_catalog(postgres_session, dataset.catalog)
    first_sales = ingest_sales(postgres_session, dataset.sales)
    second = ingest_catalog(postgres_session, dataset.catalog)
    second_sales = ingest_sales(postgres_session, dataset.sales)

    assert first.products.created == len(dataset.catalog.products)
    assert second.created == 0
    assert first_sales.rows_accepted == len(dataset.sales)
    assert second_sales.duplicate_count == len(dataset.sales)
    assert postgres_session.scalar(select(func.count()).select_from(SalesRecord)) == len(
        dataset.sales
    )
