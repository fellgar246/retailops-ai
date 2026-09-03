"""procurement reconciliation

Creates purchase orders, goods receipts, supplier invoices and the
reconciliation run/exception tables. Lines are owned by their header
(ON DELETE CASCADE). Catalog and cross-document foreign keys are
ON DELETE RESTRICT. A run owns its exceptions.

Revision ID: e8b1c03d4a29
Revises: d4e8a91c2f07
Create Date: 2026-08-30 16:00:00.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "e8b1c03d4a29"
down_revision: str | None = "d4e8a91c2f07"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _id() -> sa.types.TypeEngine[int]:
    return sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "purchase_orders",
        sa.Column("id", _id(), autoincrement=True, nullable=False),
        sa.Column("supplier_id", _id(), nullable=False),
        sa.Column("store_id", _id(), nullable=False),
        sa.Column("po_number", sa.String(length=50), nullable=False),
        sa.Column("order_date", sa.Date(), nullable=False),
        sa.Column("expected_date", sa.Date(), nullable=True),
        sa.Column("currency", sa.String(length=3), server_default=sa.text("'MXN'"), nullable=False),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'open'"), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('open', 'partial', 'received', 'closed', 'cancelled')",
            name=op.f("ck_purchase_orders_status_known"),
        ),
        sa.CheckConstraint("length(currency) = 3", name=op.f("ck_purchase_orders_currency_iso")),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["suppliers.id"],
            name=op.f("fk_purchase_orders_supplier_id_suppliers"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["store_id"],
            ["stores.id"],
            name=op.f("fk_purchase_orders_store_id_stores"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_purchase_orders")),
        sa.UniqueConstraint(
            "supplier_id", "po_number", name=op.f("uq_purchase_orders_supplier_id_po_number")
        ),
    )
    op.create_index(op.f("ix_purchase_orders_status"), "purchase_orders", ["status"], unique=False)
    op.create_index(
        op.f("ix_purchase_orders_store_id"), "purchase_orders", ["store_id"], unique=False
    )
    op.create_index(
        op.f("ix_purchase_orders_supplier_id"), "purchase_orders", ["supplier_id"], unique=False
    )

    op.create_table(
        "purchase_order_lines",
        sa.Column("id", _id(), autoincrement=True, nullable=False),
        sa.Column("purchase_order_id", _id(), nullable=False),
        sa.Column("product_id", _id(), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("ordered_quantity", sa.Integer(), nullable=False),
        sa.Column("unit_cost", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column(
            "tax_rate",
            sa.Numeric(precision=12, scale=4),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("tax_amount", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("line_total", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "line_number > 0", name=op.f("ck_purchase_order_lines_line_number_positive")
        ),
        sa.CheckConstraint(
            "ordered_quantity > 0", name=op.f("ck_purchase_order_lines_ordered_quantity_positive")
        ),
        sa.CheckConstraint(
            "unit_cost >= 0", name=op.f("ck_purchase_order_lines_unit_cost_non_negative")
        ),
        sa.CheckConstraint(
            "tax_rate >= 0", name=op.f("ck_purchase_order_lines_tax_rate_non_negative")
        ),
        sa.CheckConstraint(
            "tax_amount >= 0", name=op.f("ck_purchase_order_lines_tax_amount_non_negative")
        ),
        sa.CheckConstraint(
            "line_total >= 0", name=op.f("ck_purchase_order_lines_line_total_non_negative")
        ),
        sa.ForeignKeyConstraint(
            ["purchase_order_id"],
            ["purchase_orders.id"],
            name=op.f("fk_purchase_order_lines_purchase_order_id_purchase_orders"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_purchase_order_lines_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_purchase_order_lines")),
        sa.UniqueConstraint(
            "purchase_order_id",
            "line_number",
            name=op.f("uq_purchase_order_lines_purchase_order_id_line_number"),
        ),
    )
    op.create_index(
        op.f("ix_purchase_order_lines_product_id"),
        "purchase_order_lines",
        ["product_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_purchase_order_lines_purchase_order_id"),
        "purchase_order_lines",
        ["purchase_order_id"],
        unique=False,
    )

    op.create_table(
        "goods_receipts",
        sa.Column("id", _id(), autoincrement=True, nullable=False),
        sa.Column("supplier_id", _id(), nullable=False),
        sa.Column("purchase_order_id", _id(), nullable=True),
        sa.Column("receipt_number", sa.String(length=50), nullable=False),
        sa.Column("po_number", sa.String(length=50), nullable=True),
        sa.Column("received_date", sa.Date(), nullable=False),
        sa.Column(
            "status", sa.String(length=32), server_default=sa.text("'posted'"), nullable=False
        ),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('posted', 'cancelled')",
            name=op.f("ck_goods_receipts_status_known"),
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["suppliers.id"],
            name=op.f("fk_goods_receipts_supplier_id_suppliers"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["purchase_order_id"],
            ["purchase_orders.id"],
            name=op.f("fk_goods_receipts_purchase_order_id_purchase_orders"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_goods_receipts")),
        sa.UniqueConstraint(
            "supplier_id",
            "receipt_number",
            name=op.f("uq_goods_receipts_supplier_id_receipt_number"),
        ),
    )
    op.create_index(
        op.f("ix_goods_receipts_purchase_order_id"),
        "goods_receipts",
        ["purchase_order_id"],
        unique=False,
    )
    op.create_index(op.f("ix_goods_receipts_status"), "goods_receipts", ["status"], unique=False)
    op.create_index(
        op.f("ix_goods_receipts_supplier_id"), "goods_receipts", ["supplier_id"], unique=False
    )

    op.create_table(
        "goods_receipt_lines",
        sa.Column("id", _id(), autoincrement=True, nullable=False),
        sa.Column("goods_receipt_id", _id(), nullable=False),
        sa.Column("product_id", _id(), nullable=False),
        sa.Column("purchase_order_line_id", _id(), nullable=True),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("received_quantity", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "line_number > 0", name=op.f("ck_goods_receipt_lines_line_number_positive")
        ),
        sa.CheckConstraint(
            "received_quantity > 0", name=op.f("ck_goods_receipt_lines_received_quantity_positive")
        ),
        sa.ForeignKeyConstraint(
            ["goods_receipt_id"],
            ["goods_receipts.id"],
            name=op.f("fk_goods_receipt_lines_goods_receipt_id_goods_receipts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_goods_receipt_lines_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["purchase_order_line_id"],
            ["purchase_order_lines.id"],
            name=op.f("fk_goods_receipt_lines_purchase_order_line_id_purchase_order_lines"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_goods_receipt_lines")),
        sa.UniqueConstraint(
            "goods_receipt_id",
            "line_number",
            name=op.f("uq_goods_receipt_lines_goods_receipt_id_line_number"),
        ),
    )
    op.create_index(
        op.f("ix_goods_receipt_lines_goods_receipt_id"),
        "goods_receipt_lines",
        ["goods_receipt_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_goods_receipt_lines_product_id"),
        "goods_receipt_lines",
        ["product_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_goods_receipt_lines_purchase_order_line_id"),
        "goods_receipt_lines",
        ["purchase_order_line_id"],
        unique=False,
    )

    op.create_table(
        "supplier_invoices",
        sa.Column("id", _id(), autoincrement=True, nullable=False),
        sa.Column("supplier_id", _id(), nullable=False),
        sa.Column("purchase_order_id", _id(), nullable=True),
        sa.Column("invoice_number", sa.String(length=50), nullable=False),
        sa.Column("po_number", sa.String(length=50), nullable=True),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default=sa.text("'MXN'"), nullable=False),
        sa.Column(
            "status", sa.String(length=32), server_default=sa.text("'received'"), nullable=False
        ),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('received', 'matched', 'exception', 'cancelled')",
            name=op.f("ck_supplier_invoices_status_known"),
        ),
        sa.CheckConstraint("length(currency) = 3", name=op.f("ck_supplier_invoices_currency_iso")),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["suppliers.id"],
            name=op.f("fk_supplier_invoices_supplier_id_suppliers"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["purchase_order_id"],
            ["purchase_orders.id"],
            name=op.f("fk_supplier_invoices_purchase_order_id_purchase_orders"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_supplier_invoices")),
        sa.UniqueConstraint(
            "supplier_id",
            "invoice_number",
            name=op.f("uq_supplier_invoices_supplier_id_invoice_number"),
        ),
    )
    op.create_index(
        op.f("ix_supplier_invoices_purchase_order_id"),
        "supplier_invoices",
        ["purchase_order_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_supplier_invoices_status"), "supplier_invoices", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_supplier_invoices_supplier_id"), "supplier_invoices", ["supplier_id"], unique=False
    )

    op.create_table(
        "supplier_invoice_lines",
        sa.Column("id", _id(), autoincrement=True, nullable=False),
        sa.Column("supplier_invoice_id", _id(), nullable=False),
        sa.Column("product_id", _id(), nullable=True),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("supplier_sku", sa.String(length=64), nullable=True),
        sa.Column("ean", sa.String(length=14), nullable=True),
        sa.Column("invoiced_quantity", sa.Integer(), nullable=False),
        sa.Column("unit_cost", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column(
            "tax_rate",
            sa.Numeric(precision=12, scale=4),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("tax_amount", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("line_total", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "line_number > 0", name=op.f("ck_supplier_invoice_lines_line_number_positive")
        ),
        sa.CheckConstraint(
            "invoiced_quantity > 0",
            name=op.f("ck_supplier_invoice_lines_invoiced_quantity_positive"),
        ),
        sa.CheckConstraint(
            "unit_cost >= 0", name=op.f("ck_supplier_invoice_lines_unit_cost_non_negative")
        ),
        sa.CheckConstraint(
            "tax_rate >= 0", name=op.f("ck_supplier_invoice_lines_tax_rate_non_negative")
        ),
        sa.CheckConstraint(
            "tax_amount >= 0", name=op.f("ck_supplier_invoice_lines_tax_amount_non_negative")
        ),
        sa.CheckConstraint(
            "line_total >= 0", name=op.f("ck_supplier_invoice_lines_line_total_non_negative")
        ),
        sa.ForeignKeyConstraint(
            ["supplier_invoice_id"],
            ["supplier_invoices.id"],
            name=op.f("fk_supplier_invoice_lines_supplier_invoice_id_supplier_invoices"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_supplier_invoice_lines_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_supplier_invoice_lines")),
        sa.UniqueConstraint(
            "supplier_invoice_id",
            "line_number",
            name=op.f("uq_supplier_invoice_lines_supplier_invoice_id_line_number"),
        ),
    )
    op.create_index(
        op.f("ix_supplier_invoice_lines_product_id"),
        "supplier_invoice_lines",
        ["product_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_supplier_invoice_lines_supplier_invoice_id"),
        "supplier_invoice_lines",
        ["supplier_invoice_id"],
        unique=False,
    )

    op.create_table(
        "reconciliation_runs",
        sa.Column("id", _id(), autoincrement=True, nullable=False),
        sa.Column("scope_key", sa.String(length=200), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("input_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("purchase_order_count", sa.Integer(), nullable=False),
        sa.Column("goods_receipt_count", sa.Integer(), nullable=False),
        sa.Column("supplier_invoice_count", sa.Integer(), nullable=False),
        sa.Column("exception_count", sa.Integer(), nullable=False),
        sa.Column("error_count", sa.Integer(), nullable=False),
        sa.Column("warning_count", sa.Integer(), nullable=False),
        sa.Column("info_count", sa.Integer(), nullable=False),
        sa.Column("total_financial_impact", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("tolerances", sa.JSON(), nullable=False),
        sa.Column("run_metadata", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("version >= 1", name=op.f("ck_reconciliation_runs_version_positive")),
        sa.CheckConstraint(
            "exception_count >= 0", name=op.f("ck_reconciliation_runs_exception_count_non_negative")
        ),
        sa.CheckConstraint(
            "error_count >= 0", name=op.f("ck_reconciliation_runs_error_count_non_negative")
        ),
        sa.CheckConstraint(
            "warning_count >= 0", name=op.f("ck_reconciliation_runs_warning_count_non_negative")
        ),
        sa.CheckConstraint(
            "info_count >= 0", name=op.f("ck_reconciliation_runs_info_count_non_negative")
        ),
        sa.CheckConstraint(
            "purchase_order_count >= 0",
            name=op.f("ck_reconciliation_runs_purchase_order_count_non_negative"),
        ),
        sa.CheckConstraint(
            "goods_receipt_count >= 0",
            name=op.f("ck_reconciliation_runs_goods_receipt_count_non_negative"),
        ),
        sa.CheckConstraint(
            "supplier_invoice_count >= 0",
            name=op.f("ck_reconciliation_runs_supplier_invoice_count_non_negative"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reconciliation_runs")),
        sa.UniqueConstraint(
            "scope_key", "version", name=op.f("uq_reconciliation_runs_scope_key_version")
        ),
    )
    op.create_index(
        op.f("ix_reconciliation_runs_scope_key"),
        "reconciliation_runs",
        ["scope_key"],
        unique=False,
    )

    op.create_table(
        "reconciliation_exceptions",
        sa.Column("id", _id(), autoincrement=True, nullable=False),
        sa.Column("reconciliation_run_id", _id(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("purchase_order_id", _id(), nullable=True),
        sa.Column("purchase_order_line_id", _id(), nullable=True),
        sa.Column("goods_receipt_id", _id(), nullable=True),
        sa.Column("goods_receipt_line_id", _id(), nullable=True),
        sa.Column("supplier_invoice_id", _id(), nullable=True),
        sa.Column("supplier_invoice_line_id", _id(), nullable=True),
        sa.Column("product_id", _id(), nullable=True),
        sa.Column("expected_value", sa.String(length=64), nullable=False),
        sa.Column("actual_value", sa.String(length=64), nullable=False),
        sa.Column("financial_impact", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column(
            "resolution_status",
            sa.String(length=16),
            server_default=sa.text("'open'"),
            nullable=False,
        ),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "severity IN ('error', 'warning', 'info')",
            name=op.f("ck_reconciliation_exceptions_severity_known"),
        ),
        sa.CheckConstraint(
            "resolution_status IN ('open', 'resolved', 'dismissed')",
            name=op.f("ck_reconciliation_exceptions_resolution_known"),
        ),
        sa.ForeignKeyConstraint(
            ["reconciliation_run_id"],
            ["reconciliation_runs.id"],
            name=op.f("fk_reconciliation_exceptions_reconciliation_run_id_reconciliation_runs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["purchase_order_id"],
            ["purchase_orders.id"],
            name=op.f("fk_reconciliation_exceptions_purchase_order_id_purchase_orders"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["purchase_order_line_id"],
            ["purchase_order_lines.id"],
            name=op.f("fk_reconciliation_exceptions_purchase_order_line_id_purchase_order_lines"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["goods_receipt_id"],
            ["goods_receipts.id"],
            name=op.f("fk_reconciliation_exceptions_goods_receipt_id_goods_receipts"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["goods_receipt_line_id"],
            ["goods_receipt_lines.id"],
            name=op.f("fk_reconciliation_exceptions_goods_receipt_line_id_goods_receipt_lines"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["supplier_invoice_id"],
            ["supplier_invoices.id"],
            name=op.f("fk_reconciliation_exceptions_supplier_invoice_id_supplier_invoices"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["supplier_invoice_line_id"],
            ["supplier_invoice_lines.id"],
            name=op.f(
                "fk_reconciliation_exceptions_supplier_invoice_line_id_supplier_invoice_lines"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_reconciliation_exceptions_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reconciliation_exceptions")),
    )
    op.create_index(
        op.f("ix_reconciliation_exceptions_code"),
        "reconciliation_exceptions",
        ["code"],
        unique=False,
    )
    op.create_index(
        op.f("ix_reconciliation_exceptions_goods_receipt_id"),
        "reconciliation_exceptions",
        ["goods_receipt_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_reconciliation_exceptions_goods_receipt_line_id"),
        "reconciliation_exceptions",
        ["goods_receipt_line_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_reconciliation_exceptions_product_id"),
        "reconciliation_exceptions",
        ["product_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_reconciliation_exceptions_purchase_order_id"),
        "reconciliation_exceptions",
        ["purchase_order_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_reconciliation_exceptions_purchase_order_line_id"),
        "reconciliation_exceptions",
        ["purchase_order_line_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_reconciliation_exceptions_reconciliation_run_id"),
        "reconciliation_exceptions",
        ["reconciliation_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_reconciliation_exceptions_resolution_status"),
        "reconciliation_exceptions",
        ["resolution_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_reconciliation_exceptions_supplier_invoice_id"),
        "reconciliation_exceptions",
        ["supplier_invoice_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_reconciliation_exceptions_supplier_invoice_line_id"),
        "reconciliation_exceptions",
        ["supplier_invoice_line_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_reconciliation_exceptions_supplier_invoice_line_id"),
        table_name="reconciliation_exceptions",
    )
    op.drop_index(
        op.f("ix_reconciliation_exceptions_supplier_invoice_id"),
        table_name="reconciliation_exceptions",
    )
    op.drop_index(
        op.f("ix_reconciliation_exceptions_resolution_status"),
        table_name="reconciliation_exceptions",
    )
    op.drop_index(
        op.f("ix_reconciliation_exceptions_reconciliation_run_id"),
        table_name="reconciliation_exceptions",
    )
    op.drop_index(
        op.f("ix_reconciliation_exceptions_purchase_order_line_id"),
        table_name="reconciliation_exceptions",
    )
    op.drop_index(
        op.f("ix_reconciliation_exceptions_purchase_order_id"),
        table_name="reconciliation_exceptions",
    )
    op.drop_index(
        op.f("ix_reconciliation_exceptions_product_id"), table_name="reconciliation_exceptions"
    )
    op.drop_index(
        op.f("ix_reconciliation_exceptions_goods_receipt_line_id"),
        table_name="reconciliation_exceptions",
    )
    op.drop_index(
        op.f("ix_reconciliation_exceptions_goods_receipt_id"),
        table_name="reconciliation_exceptions",
    )
    op.drop_index(op.f("ix_reconciliation_exceptions_code"), table_name="reconciliation_exceptions")
    op.drop_table("reconciliation_exceptions")
    op.drop_index(op.f("ix_reconciliation_runs_scope_key"), table_name="reconciliation_runs")
    op.drop_table("reconciliation_runs")
    op.drop_index(
        op.f("ix_supplier_invoice_lines_supplier_invoice_id"), table_name="supplier_invoice_lines"
    )
    op.drop_index(op.f("ix_supplier_invoice_lines_product_id"), table_name="supplier_invoice_lines")
    op.drop_table("supplier_invoice_lines")
    op.drop_index(op.f("ix_supplier_invoices_supplier_id"), table_name="supplier_invoices")
    op.drop_index(op.f("ix_supplier_invoices_status"), table_name="supplier_invoices")
    op.drop_index(op.f("ix_supplier_invoices_purchase_order_id"), table_name="supplier_invoices")
    op.drop_table("supplier_invoices")
    op.drop_index(
        op.f("ix_goods_receipt_lines_purchase_order_line_id"), table_name="goods_receipt_lines"
    )
    op.drop_index(op.f("ix_goods_receipt_lines_product_id"), table_name="goods_receipt_lines")
    op.drop_index(op.f("ix_goods_receipt_lines_goods_receipt_id"), table_name="goods_receipt_lines")
    op.drop_table("goods_receipt_lines")
    op.drop_index(op.f("ix_goods_receipts_supplier_id"), table_name="goods_receipts")
    op.drop_index(op.f("ix_goods_receipts_status"), table_name="goods_receipts")
    op.drop_index(op.f("ix_goods_receipts_purchase_order_id"), table_name="goods_receipts")
    op.drop_table("goods_receipts")
    op.drop_index(
        op.f("ix_purchase_order_lines_purchase_order_id"), table_name="purchase_order_lines"
    )
    op.drop_index(op.f("ix_purchase_order_lines_product_id"), table_name="purchase_order_lines")
    op.drop_table("purchase_order_lines")
    op.drop_index(op.f("ix_purchase_orders_supplier_id"), table_name="purchase_orders")
    op.drop_index(op.f("ix_purchase_orders_store_id"), table_name="purchase_orders")
    op.drop_index(op.f("ix_purchase_orders_status"), table_name="purchase_orders")
    op.drop_table("purchase_orders")
