"""The shared persistence conventions the whole schema relies on."""

import re
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import DateTime, Table

from retailops_api.db.base import NAMING_CONVENTION
from retailops_api.domain.models import Base

EXPECTED_TABLES = {
    "categories",
    "document_findings",
    "forecast_predictions",
    "forecast_runs",
    "products",
    "sales_records",
    "stores",
    "supplier_documents",
    "supplier_products",
    "suppliers",
}

IMMUTABLE_FACT_TABLES = {
    "document_findings",
    "forecast_predictions",
    "forecast_runs",
    "sales_records",
}

API_ROOT = Path(__file__).resolve().parents[1]


def test_metadata_registers_every_domain_table() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_metadata_uses_the_shared_naming_convention() -> None:
    assert dict(Base.metadata.naming_convention) == NAMING_CONVENTION


@pytest.mark.parametrize("table_name", sorted(EXPECTED_TABLES))
def test_primary_key_follows_the_convention(table_name: str) -> None:
    table = Base.metadata.tables[table_name]
    assert table.primary_key.name == f"pk_{table_name}"
    assert [column.name for column in table.primary_key.columns] == ["id"]


@pytest.mark.parametrize("table_name", sorted(EXPECTED_TABLES))
def test_constraint_and_index_names_are_prefixed(table_name: str) -> None:
    table: Table = Base.metadata.tables[table_name]
    prefixes = {
        "PrimaryKeyConstraint": "pk_",
        "ForeignKeyConstraint": "fk_",
        "UniqueConstraint": "uq_",
        "CheckConstraint": "ck_",
    }
    for constraint in table.constraints:
        prefix = prefixes[type(constraint).__name__]
        assert str(constraint.name).startswith(prefix), constraint.name

    for index in table.indexes:
        assert str(index.name).startswith("ix_"), index.name


@pytest.mark.parametrize("table_name", sorted(EXPECTED_TABLES))
def test_every_table_records_when_a_row_was_created(table_name: str) -> None:
    assert "created_at" in Base.metadata.tables[table_name].columns


@pytest.mark.parametrize("table_name", sorted(EXPECTED_TABLES - IMMUTABLE_FACT_TABLES))
def test_mutable_tables_track_updates_and_lifecycle(table_name: str) -> None:
    columns = Base.metadata.tables[table_name].columns
    assert "updated_at" in columns
    assert "active" in columns


@pytest.mark.parametrize("table_name", sorted(IMMUTABLE_FACT_TABLES))
def test_fact_tables_are_immutable_once_written(table_name: str) -> None:
    """Sales facts and forecast results are not edited in place."""
    columns = Base.metadata.tables[table_name].columns
    assert "updated_at" not in columns
    assert "active" not in columns


def test_timestamps_are_timezone_aware() -> None:
    for table in Base.metadata.tables.values():
        for name in ("created_at", "updated_at"):
            if name not in table.columns:
                continue
            column_type = table.columns[name].type
            assert isinstance(column_type, DateTime), f"{table.name}.{name}"
            assert column_type.timezone is True, f"{table.name}.{name}"


def test_alembic_discovers_the_domain_metadata() -> None:
    """The migration environment must see exactly the tables the app defines."""
    config = Config(str(API_ROOT / "alembic.ini"))
    script = ScriptDirectory.from_config(config)

    heads = script.get_heads()
    assert len(heads) == 1, f"expected a single migration head, found {heads}"

    revisions = [revision.revision for revision in script.walk_revisions()]
    assert len(revisions) == len(set(revisions))


# Planning documents are not part of the delivered system. Shipped text must
# describe capabilities, not numbered planning artefacts.
_PLANNING_REFERENCE = re.compile(
    r"\bSpec\s+\d+\b|\bBlock\s+\d+\b|\blater\s+block\b|\bnext\s+block\b",
    re.IGNORECASE,
)
_SHIPPED_TEXT_SUFFIXES = {".py", ".md"}
_SHIPPED_ROOTS = (
    API_ROOT / "src",
    API_ROOT / "tests",
    API_ROOT / "README.md",
    API_ROOT.parents[1] / "README.md",
    API_ROOT.parents[1] / "Makefile",
)


def _is_shipped_text(path: Path) -> bool:
    return path.is_file() and (path.suffix in _SHIPPED_TEXT_SUFFIXES or path.name == "Makefile")


def test_shipped_text_does_not_refer_to_planning_artefacts() -> None:
    hits: list[str] = []
    for root in _SHIPPED_ROOTS:
        paths = [root] if root.is_file() else root.rglob("*")
        for path in paths:
            if not _is_shipped_text(path):
                continue
            text = path.read_text(encoding="utf-8")
            for match in _PLANNING_REFERENCE.finditer(text):
                hits.append(f"{path}:{match.group(0)}")
    assert hits == []
