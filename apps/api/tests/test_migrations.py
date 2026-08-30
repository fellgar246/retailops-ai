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
    "document_findings",
    "forecast_predictions",
    "forecast_runs",
    "goods_receipt_lines",
    "goods_receipts",
    "products",
    "purchase_order_lines",
    "purchase_orders",
    "reconciliation_exceptions",
    "reconciliation_runs",
    "review_ai_snapshots",
    "review_audit_events",
    "review_cases",
    "review_decisions",
    "sales_records",
    "stores",
    "supplier_documents",
    "supplier_invoice_lines",
    "supplier_invoices",
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
        (
            "supplier_documents",
            {"ix_supplier_documents_status", "ix_supplier_documents_supplier_id"},
        ),
        ("document_findings", {"ix_document_findings_document_id"}),
        (
            "purchase_orders",
            {
                "ix_purchase_orders_status",
                "ix_purchase_orders_store_id",
                "ix_purchase_orders_supplier_id",
            },
        ),
        (
            "purchase_order_lines",
            {
                "ix_purchase_order_lines_product_id",
                "ix_purchase_order_lines_purchase_order_id",
            },
        ),
        (
            "goods_receipts",
            {
                "ix_goods_receipts_purchase_order_id",
                "ix_goods_receipts_status",
                "ix_goods_receipts_supplier_id",
            },
        ),
        (
            "goods_receipt_lines",
            {
                "ix_goods_receipt_lines_goods_receipt_id",
                "ix_goods_receipt_lines_product_id",
                "ix_goods_receipt_lines_purchase_order_line_id",
            },
        ),
        (
            "supplier_invoices",
            {
                "ix_supplier_invoices_purchase_order_id",
                "ix_supplier_invoices_status",
                "ix_supplier_invoices_supplier_id",
            },
        ),
        (
            "supplier_invoice_lines",
            {
                "ix_supplier_invoice_lines_product_id",
                "ix_supplier_invoice_lines_supplier_invoice_id",
            },
        ),
        ("reconciliation_runs", {"ix_reconciliation_runs_scope_key"}),
        (
            "reconciliation_exceptions",
            {
                "ix_reconciliation_exceptions_code",
                "ix_reconciliation_exceptions_reconciliation_run_id",
                "ix_reconciliation_exceptions_resolution_status",
            },
        ),
        (
            "review_cases",
            {
                "ix_review_cases_created_at",
                "ix_review_cases_priority",
                "ix_review_cases_risk",
                "ix_review_cases_status",
                "ix_review_cases_subject_type",
                "ix_review_cases_supplier_id",
            },
        ),
        (
            "review_decisions",
            {"ix_review_decisions_snapshot_id"},
        ),
        (
            "review_audit_events",
            {
                "ix_review_audit_events_event_type",
                "ix_review_audit_events_review_case_id",
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
        ("supplier_documents", {("supplier_id",): "suppliers"}),
        ("document_findings", {("document_id",): "supplier_documents"}),
        ("purchase_orders", {("supplier_id",): "suppliers", ("store_id",): "stores"}),
        (
            "purchase_order_lines",
            {("purchase_order_id",): "purchase_orders", ("product_id",): "products"},
        ),
        (
            "goods_receipts",
            {("supplier_id",): "suppliers", ("purchase_order_id",): "purchase_orders"},
        ),
        (
            "goods_receipt_lines",
            {
                ("goods_receipt_id",): "goods_receipts",
                ("product_id",): "products",
                ("purchase_order_line_id",): "purchase_order_lines",
            },
        ),
        (
            "supplier_invoices",
            {("supplier_id",): "suppliers", ("purchase_order_id",): "purchase_orders"},
        ),
        (
            "supplier_invoice_lines",
            {("supplier_invoice_id",): "supplier_invoices", ("product_id",): "products"},
        ),
        (
            "reconciliation_exceptions",
            {
                ("reconciliation_run_id",): "reconciliation_runs",
                ("purchase_order_id",): "purchase_orders",
                ("purchase_order_line_id",): "purchase_order_lines",
                ("goods_receipt_id",): "goods_receipts",
                ("goods_receipt_line_id",): "goods_receipt_lines",
                ("supplier_invoice_id",): "supplier_invoices",
                ("supplier_invoice_line_id",): "supplier_invoice_lines",
                ("product_id",): "products",
            },
        ),
        (
            "review_cases",
            {
                ("document_finding_id",): "document_findings",
                ("reconciliation_exception_id",): "reconciliation_exceptions",
                ("supplier_id",): "suppliers",
            },
        ),
        ("review_ai_snapshots", {("review_case_id",): "review_cases"}),
        (
            "review_decisions",
            {
                ("review_case_id",): "review_cases",
                ("snapshot_id",): "review_ai_snapshots",
            },
        ),
        ("review_audit_events", {("review_case_id",): "review_cases"}),
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


def test_document_findings_are_removed_with_their_document(migrated: URL) -> None:
    """A document owns its findings; they have no meaning once the file record is gone."""
    foreign_keys = _inspector(migrated).get_foreign_keys("document_findings")

    assert len(foreign_keys) == 1
    assert foreign_keys[0]["options"].get("ondelete") == "CASCADE"


def test_supplier_documents_restrict_supplier_deletes(migrated: URL) -> None:
    """A stored file keeps its supplier row; retirement is deactivation."""
    for fk in _inspector(migrated).get_foreign_keys("supplier_documents"):
        assert fk["options"].get("ondelete") == "RESTRICT", fk["name"]


def test_purchase_order_lines_are_removed_with_their_order(migrated: URL) -> None:
    foreign_keys = {
        tuple(fk["constrained_columns"]): fk["options"].get("ondelete")
        for fk in _inspector(migrated).get_foreign_keys("purchase_order_lines")
    }
    assert foreign_keys[("purchase_order_id",)] == "CASCADE"
    assert foreign_keys[("product_id",)] == "RESTRICT"


def test_receipt_and_invoice_lines_are_removed_with_their_header(migrated: URL) -> None:
    receipt = {
        tuple(fk["constrained_columns"]): fk["options"].get("ondelete")
        for fk in _inspector(migrated).get_foreign_keys("goods_receipt_lines")
    }
    invoice = {
        tuple(fk["constrained_columns"]): fk["options"].get("ondelete")
        for fk in _inspector(migrated).get_foreign_keys("supplier_invoice_lines")
    }
    assert receipt[("goods_receipt_id",)] == "CASCADE"
    assert invoice[("supplier_invoice_id",)] == "CASCADE"


def test_reconciliation_exceptions_are_removed_with_their_run(migrated: URL) -> None:
    """A run owns its exceptions; they have no meaning once the run is gone."""
    foreign_keys = _inspector(migrated).get_foreign_keys("reconciliation_exceptions")
    run_fk = next(
        fk for fk in foreign_keys if fk["constrained_columns"] == ["reconciliation_run_id"]
    )
    assert run_fk["options"].get("ondelete") == "CASCADE"


def test_review_history_is_removed_with_its_case(migrated: URL) -> None:
    """Snapshots, decisions and audit events belong to the case."""
    for table_name, column in (
        ("review_ai_snapshots", "review_case_id"),
        ("review_decisions", "review_case_id"),
        ("review_audit_events", "review_case_id"),
    ):
        foreign_keys = _inspector(migrated).get_foreign_keys(table_name)
        case_fk = next(fk for fk in foreign_keys if fk["constrained_columns"] == [column])
        assert case_fk["options"].get("ondelete") == "CASCADE"


def test_review_cases_restrict_subject_deletes(migrated: URL) -> None:
    """A reviewed finding or exception cannot disappear from under the case."""
    foreign_keys = {
        tuple(fk["constrained_columns"]): fk["options"].get("ondelete")
        for fk in _inspector(migrated).get_foreign_keys("review_cases")
    }
    assert foreign_keys[("document_finding_id",)] == "RESTRICT"
    assert foreign_keys[("reconciliation_exception_id",)] == "RESTRICT"
    assert foreign_keys[("supplier_id",)] == "RESTRICT"


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
        ("supplier_documents", {"uq_supplier_documents_storage_key"}),
        ("purchase_orders", {"uq_purchase_orders_supplier_id_po_number"}),
        ("purchase_order_lines", {"uq_purchase_order_lines_purchase_order_id_line_number"}),
        ("goods_receipts", {"uq_goods_receipts_supplier_id_receipt_number"}),
        ("goods_receipt_lines", {"uq_goods_receipt_lines_goods_receipt_id_line_number"}),
        ("supplier_invoices", {"uq_supplier_invoices_supplier_id_invoice_number"}),
        (
            "supplier_invoice_lines",
            {"uq_supplier_invoice_lines_supplier_invoice_id_line_number"},
        ),
        ("reconciliation_runs", {"uq_reconciliation_runs_scope_key_version"}),
        (
            "review_cases",
            {
                "uq_review_cases_document_finding_id",
                "uq_review_cases_reconciliation_exception_id",
            },
        ),
        ("review_ai_snapshots", {"uq_review_ai_snapshots_review_case_id"}),
        ("review_decisions", {"uq_review_decisions_review_case_id"}),
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
        (
            "supplier_documents",
            {
                "ck_supplier_documents_document_type_known",
                "ck_supplier_documents_status_known",
            },
        ),
        ("document_findings", {"ck_document_findings_severity_known"}),
        (
            "purchase_orders",
            {"ck_purchase_orders_status_known", "ck_purchase_orders_currency_iso"},
        ),
        (
            "purchase_order_lines",
            {
                "ck_purchase_order_lines_line_number_positive",
                "ck_purchase_order_lines_ordered_quantity_positive",
                "ck_purchase_order_lines_unit_cost_non_negative",
            },
        ),
        ("goods_receipts", {"ck_goods_receipts_status_known"}),
        (
            "goods_receipt_lines",
            {
                "ck_goods_receipt_lines_line_number_positive",
                "ck_goods_receipt_lines_received_quantity_positive",
            },
        ),
        (
            "supplier_invoices",
            {"ck_supplier_invoices_status_known", "ck_supplier_invoices_currency_iso"},
        ),
        (
            "supplier_invoice_lines",
            {
                "ck_supplier_invoice_lines_line_number_positive",
                "ck_supplier_invoice_lines_invoiced_quantity_positive",
                "ck_supplier_invoice_lines_unit_cost_non_negative",
            },
        ),
        (
            "reconciliation_runs",
            {
                "ck_reconciliation_runs_version_positive",
                "ck_reconciliation_runs_exception_count_non_negative",
            },
        ),
        (
            "reconciliation_exceptions",
            {
                "ck_reconciliation_exceptions_severity_known",
                "ck_reconciliation_exceptions_resolution_known",
            },
        ),
        (
            "review_cases",
            {
                "ck_review_cases_status_known",
                "ck_review_cases_priority_known",
                "ck_review_cases_subject_type_known",
                "ck_review_cases_risk_known",
                "ck_review_cases_subject_matches_type",
                "ck_review_cases_confidence_unit_interval",
            },
        ),
        ("review_ai_snapshots", {"ck_review_ai_snapshots_confidence_unit_interval"}),
        (
            "review_decisions",
            {
                "ck_review_decisions_decision_known",
                "ck_review_decisions_reject_requires_reason",
                "ck_review_decisions_correct_requires_payload",
            },
        ),
        ("review_audit_events", {"ck_review_audit_events_event_type_known"}),
    ],
)
def test_check_constraints_exist(migrated: URL, table_name: str, expected: set[str]) -> None:
    actual = {
        constraint["name"] for constraint in _inspector(migrated).get_check_constraints(table_name)
    }

    assert expected <= actual
