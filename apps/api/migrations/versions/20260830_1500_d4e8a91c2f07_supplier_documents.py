"""supplier documents

Creates supplier_documents and document_findings so a stored supplier file
can be reviewed deterministically. Findings are owned by the document
(ON DELETE CASCADE). The supplier foreign key is ON DELETE RESTRICT.

Revision ID: d4e8a91c2f07
Revises: c7e4f19a2b08
Create Date: 2026-08-30 15:00:00.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "d4e8a91c2f07"
down_revision: str | None = "c7e4f19a2b08"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "supplier_documents",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "supplier_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("media_type", sa.String(length=127), nullable=False),
        sa.Column("storage_key", sa.String(length=64), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("document_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
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
            "document_type IN ('supplier_sheet')",
            name=op.f("ck_supplier_documents_document_type_known"),
        ),
        sa.CheckConstraint(
            "status IN ('received', 'parsed', 'parse_failed', 'validated', 'review_ready')",
            name=op.f("ck_supplier_documents_status_known"),
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["suppliers.id"],
            name=op.f("fk_supplier_documents_supplier_id_suppliers"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_supplier_documents")),
        sa.UniqueConstraint("storage_key", name=op.f("uq_supplier_documents_storage_key")),
    )
    op.create_index(
        op.f("ix_supplier_documents_status"),
        "supplier_documents",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_supplier_documents_supplier_id"),
        "supplier_documents",
        ["supplier_id"],
        unique=False,
    )
    op.create_table(
        "document_findings",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "document_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            nullable=False,
        ),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("field", sa.String(length=64), nullable=True),
        sa.Column("row_reference", sa.Integer(), nullable=True),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("proposed_value", sa.String(length=200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "severity IN ('error', 'warning', 'info')",
            name=op.f("ck_document_findings_severity_known"),
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["supplier_documents.id"],
            name=op.f("fk_document_findings_document_id_supplier_documents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_findings")),
    )
    op.create_index(
        op.f("ix_document_findings_document_id"),
        "document_findings",
        ["document_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_document_findings_document_id"), table_name="document_findings")
    op.drop_table("document_findings")
    op.drop_index(op.f("ix_supplier_documents_supplier_id"), table_name="supplier_documents")
    op.drop_index(op.f("ix_supplier_documents_status"), table_name="supplier_documents")
    op.drop_table("supplier_documents")
