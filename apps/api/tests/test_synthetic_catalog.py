"""The synthetic catalog is deterministic and satisfies the dataset contract."""

from retailops_api.dataset.validate import validate_catalog
from retailops_api.synthetic.catalog import generate_catalog
from retailops_api.synthetic.config import GeneratorConfig


def _tiny(**overrides: object) -> GeneratorConfig:
    return GeneratorConfig.from_preset("tiny", **overrides)


def test_the_same_seed_produces_the_same_catalog() -> None:
    first = generate_catalog(_tiny())
    second = generate_catalog(_tiny())

    assert first.catalog == second.catalog
    assert first.list_price == second.list_price
    assert first.popularity == second.popularity


def test_a_different_seed_changes_latent_factors() -> None:
    first = generate_catalog(_tiny(seed=1))
    second = generate_catalog(_tiny(seed=2))

    assert first.popularity != second.popularity


def test_changing_the_date_range_does_not_reshuffle_the_catalog() -> None:
    from datetime import date

    first = generate_catalog(_tiny())
    second = generate_catalog(_tiny(start_date=date(2024, 1, 1), end_date=date(2024, 1, 31)))

    assert first.catalog == second.catalog


def test_requested_counts_are_honoured() -> None:
    artifacts = generate_catalog(
        _tiny(store_count=3, product_count=10, supplier_count=2, category_count=6)
    )

    assert len(artifacts.catalog.stores) == 3
    assert len(artifacts.catalog.products) == 10
    assert len(artifacts.catalog.suppliers) == 2
    assert len(artifacts.catalog.categories) == 6


def test_the_category_tree_has_roots_and_leaves() -> None:
    catalog = generate_catalog(_tiny()).catalog
    roots = [row for row in catalog.categories if row.parent_code is None]
    children = [row for row in catalog.categories if row.parent_code is not None]

    assert roots
    assert children
    parent_codes = {row.code for row in catalog.categories}
    for child in children:
        assert child.parent_code in parent_codes


def test_products_hang_off_categories_that_exist() -> None:
    catalog = generate_catalog(_tiny()).catalog
    codes = {row.code for row in catalog.categories}

    for product in catalog.products:
        assert product.category_code in codes


def test_every_product_has_supplier_terms() -> None:
    catalog = generate_catalog(_tiny()).catalog
    covered = {row.product_sku for row in catalog.supplier_products}

    assert covered == {product.sku for product in catalog.products}


def test_at_least_one_product_has_two_suppliers() -> None:
    catalog = generate_catalog(_tiny()).catalog
    counts: dict[str, int] = {}
    for row in catalog.supplier_products:
        counts[row.product_sku] = counts.get(row.product_sku, 0) + 1

    assert any(count > 1 for count in counts.values())


def test_at_least_one_product_has_no_barcode() -> None:
    catalog = generate_catalog(_tiny()).catalog

    assert any(product.ean is None for product in catalog.products)


def test_at_least_one_supplier_has_no_tax_id() -> None:
    catalog = generate_catalog(_tiny(supplier_count=4)).catalog

    assert any(supplier.tax_id is None for supplier in catalog.suppliers)


def test_stores_cover_more_than_one_region_and_type() -> None:
    catalog = generate_catalog(_tiny(store_count=4)).catalog

    assert len({store.region for store in catalog.stores}) > 1
    assert len({store.store_type for store in catalog.stores}) > 1


def test_generated_catalog_passes_validation() -> None:
    catalog = generate_catalog(_tiny()).catalog

    assert validate_catalog(catalog) == []


def test_money_and_quantities_honour_domain_constraints() -> None:
    catalog = generate_catalog(_tiny()).catalog

    for row in catalog.supplier_products:
        assert row.cost >= 0
        assert row.case_pack > 0
        assert row.minimum_order_quantity >= 0
        assert row.lead_time_days >= 0
