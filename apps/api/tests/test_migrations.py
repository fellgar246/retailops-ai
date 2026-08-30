"""The domain migration, exercised against real PostgreSQL.

Every test here runs against a throwaway database created by the fixtures, so
the developer's own data is never migrated or dropped.
"""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Inspector, create_engine, inspect
from sqlalchemy.engine import URL

from tests.conftest import requires_postgres

pytestmark = requires_postgres

API_ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP_REVISION = "6424a6340d6e"

DOMAIN_TABLES = {
    "categories",
    "forecast_predictions",
    "forecast_runs",
    "products",
    "sales_records",
    "stores",
    "supplier_products",
    "suppliers",
}


def _config(url: URL) -> Config:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", url.render_as_string(hide_password=False))
    return config


def _table_names(url: URL) -> set[str]:
    engine = create_engine(url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def _current_revision(url: URL) -> str | None:
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            return MigrationContext.configure(connection).get_current_revision()
    finally:
        engine.dispose()


@pytest.fixture
def migrated(postgres_migration_url: URL) -> URL:
    command.upgrade(_config(postgres_migration_url), "head")
    return postgres_migration_url


def test_upgrade_from_the_bootstrap_revision_creates_the_schema(
    postgres_migration_url: URL,
) -> None:
    config = _config(postgres_migration_url)

    command.upgrade(config, BOOTSTRAP_REVISION)
    assert _table_names(postgres_migration_url) == {"alembic_version"}

    command.upgrade(config, "head")
    assert DOMAIN_TABLES.issubset(_table_names(postgres_migration_url))


def test_downgrade_removes_the_schema(migrated: URL) -> None:
    command.downgrade(_config(migrated), BOOTSTRAP_REVISION)

    assert _table_names(migrated) == {"alembic_version"}
    assert _current_revision(migrated) == BOOTSTRAP_REVISION


def test_upgrade_downgrade_upgrade_is_repeatable(migrated: URL) -> None:
    config = _config(migrated)
    head = ScriptDirectory.from_config(config).get_current_head()

    command.downgrade(config, BOOTSTRAP_REVISION)
    command.upgrade(config, "head")

    assert DOMAIN_TABLES.issubset(_table_names(migrated))
    assert _current_revision(migrated) == head


def test_downgrade_to_base_leaves_nothing_behind(migrated: URL) -> None:
    command.downgrade(_config(migrated), "base")

    assert _table_names(migrated) == {"alembic_version"}
    assert _current_revision(migrated) is None


def test_the_migration_matches_the_models(migrated: URL) -> None:
    """`alembic check` fails if the models have drifted from the migrations."""
    command.check(_config(migrated))


def _inspector(url: URL) -> Inspector:
    return inspect(create_engine(url))


@pytest.mark.parametrize("table_name", sorted(DOMAIN_TABLES))
def test_every_table_has_its_primary_key(migrated: URL, table_name: str) -> None:
    primary_key = _inspector(migrated).get_pk_constraint(table_name)

    assert primary_key["name"] == f"pk_{table_name}"
    assert primary_key["constrained_columns"] == ["id"]


@pytest.mark.parametrize(
    ("table_name", "expected"),
    [
        ("categories", {"ix_categories_parent_id"}),
        ("products", {"ix_products_category_id"}),
        ("stores", {"ix_stores_region", "ix_stores_store_type"}),
        (
            "sales_records",
            {
                "ix_sales_records_business_date",
                "ix_sales_records_product_id",
                "ix_sales_records_store_id",
            },
        ),
        (
            "supplier_products",
            {"ix_supplier_products_product_id", "ix_supplier_products_supplier_id"},
        ),
        (
            "forecast_runs",
            {"ix_forecast_runs_cutoff", "ix_forecast_runs_model_id"},
        ),
        (
            "forecast_predictions",
            {
                "ix_forecast_predictions_forecast_run_id",
                "ix_forecast_predictions_period_start",
            },
        ),
    ],
)
def test_expected_indexes_exist(migrated: URL, table_name: str, expected: set[str]) -> None:
    actual = {index["name"] for index in _inspector(migrated).get_indexes(table_name)}

    assert expected <= actual


@pytest.mark.parametrize(
    ("table_name", "expected"),
    [
        ("categories", {("parent_id",): "categories"}),
        ("products", {("category_id",): "categories"}),
        ("sales_records", {("store_id",): "stores", ("product_id",): "products"}),
        ("supplier_products", {("supplier_id",): "suppliers", ("product_id",): "products"}),
        ("forecast_predictions", {("forecast_run_id",): "forecast_runs"}),
    ],
)
def test_foreign_keys_point_where_they_should(
    migrated: URL, table_name: str, expected: dict[tuple[str, ...], str]
) -> None:
    actual = {
        tuple(fk["constrained_columns"]): fk["referred_table"]
        for fk in _inspector(migrated).get_foreign_keys(table_name)
    }

    assert actual == expected


@pytest.mark.parametrize("table_name", ["categories", "products", "sales_records"])
def test_foreign_keys_restrict_deletes(migrated: URL, table_name: str) -> None:
    """Catalog rows referenced by history must not be deletable. See ADR-002."""
    for fk in _inspector(migrated).get_foreign_keys(table_name):
        assert fk["options"].get("ondelete") == "RESTRICT", fk["name"]


def test_forecast_predictions_are_removed_with_their_run(migrated: URL) -> None:
    """A run owns its predictions; they have no meaning once the run is gone."""
    foreign_keys = _inspector(migrated).get_foreign_keys("forecast_predictions")

    assert len(foreign_keys) == 1
    assert foreign_keys[0]["options"].get("ondelete") == "CASCADE"


@pytest.mark.parametrize(
    ("table_name", "expected"),
    [
        ("categories", {"uq_categories_code"}),
        ("products", {"uq_products_sku", "uq_products_ean"}),
        ("stores", {"uq_stores_code"}),
        ("suppliers", {"uq_suppliers_code"}),
        ("supplier_products", {"uq_supplier_products_supplier_id_product_id"}),
        ("sales_records", {"uq_sales_records_store_id_product_id_business_date"}),
        (
            "forecast_predictions",
            {"uq_forecast_predictions_run_entity_week"},
        ),
    ],
)
def test_unique_constraints_exist(migrated: URL, table_name: str, expected: set[str]) -> None:
    actual = {
        constraint["name"] for constraint in _inspector(migrated).get_unique_constraints(table_name)
    }

    assert expected <= actual


@pytest.mark.parametrize(
    ("table_name", "expected"),
    [
        ("categories", {"ck_categories_parent_not_self"}),
        (
            "supplier_products",
            {
                "ck_supplier_products_cost_non_negative",
                "ck_supplier_products_case_pack_positive",
                "ck_supplier_products_min_order_qty_non_negative",
                "ck_supplier_products_lead_time_days_non_negative",
            },
        ),
        (
            "sales_records",
            {
                "ck_sales_records_units_sold_non_negative",
                "ck_sales_records_unit_price_non_negative",
                "ck_sales_records_discount_amount_non_negative",
                "ck_sales_records_stock_on_hand_non_negative",
            },
        ),
        ("forecast_runs", {"ck_forecast_runs_horizon_positive"}),
        (
            "forecast_predictions",
            {
                "ck_forecast_predictions_step_positive",
                "ck_forecast_predictions_predicted_non_negative",
                "ck_forecast_predictions_actual_non_negative",
            },
        ),
    ],
)
def test_check_constraints_exist(migrated: URL, table_name: str, expected: set[str]) -> None:
    actual = {
        constraint["name"] for constraint in _inspector(migrated).get_check_constraints(table_name)
    }

    assert expected <= actual
