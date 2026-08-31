import os
from collections.abc import Iterator

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from retailops_api.api.deps import get_db
from retailops_api.core.config import get_settings
from retailops_api.domain.models import Base
from retailops_api.main import create_app

#: Scratch database for the PostgreSQL integration tests. Created and dropped by
#: the fixtures below so the developer's own database is never touched.
POSTGRES_TEST_DATABASE = "retailops_test"

#: Separate database again for migration tests, which drop every table.
POSTGRES_MIGRATION_DATABASE = "retailops_migration_test"


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


@pytest.fixture
def api_client(app: FastAPI, session: Session) -> Iterator[TestClient]:
    def _override() -> Iterator[Session]:
        yield session
        session.commit()

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# --------------------------------------------------------------------------- #
# SQLite: fast, hermetic coverage of the mapping and every constraint
# --------------------------------------------------------------------------- #


@pytest.fixture
def engine() -> Iterator[Engine]:
    """In-memory SQLite engine with the full domain schema."""
    sqlite_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        # A single shared connection keeps the in-memory database alive for the
        # whole test and lets `create_all` and the session see the same schema.
        poolclass=StaticPool,
    )

    # SQLite ignores foreign keys unless asked, which would silently pass tests
    # that exist to prove referential integrity.
    @event.listens_for(sqlite_engine, "connect")
    def _enable_foreign_keys(dbapi_connection: object, _record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(sqlite_engine)
    try:
        yield sqlite_engine
    finally:
        sqlite_engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with Session(engine, expire_on_commit=False) as db_session:
        yield db_session


# --------------------------------------------------------------------------- #
# PostgreSQL: the dialect the application actually runs on
# --------------------------------------------------------------------------- #


def _server_url() -> URL:
    """Connection URL for the configured server, pointing at its default database."""
    return make_url(get_settings().database_url)


def _postgres_reachable() -> bool:
    if os.environ.get("RETAILOPS_SKIP_POSTGRES_TESTS"):
        return False
    try:
        engine = create_engine(_server_url(), connect_args={"connect_timeout": 2})
        with engine.connect():
            pass
        engine.dispose()
    except Exception:
        return False
    return True


requires_postgres = pytest.mark.skipif(
    not _postgres_reachable(),
    reason="PostgreSQL is not reachable; run `make db-up` to enable these tests",
)


def _recreate_database(name: str) -> URL:
    """Drop and recreate ``name`` on the configured server, returning its URL."""
    admin = create_engine(_server_url(), isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(sa.text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        connection.execute(sa.text(f'CREATE DATABASE "{name}"'))
    admin.dispose()
    return _server_url().set(database=name)


def _drop_database(name: str) -> None:
    admin = create_engine(_server_url(), isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(sa.text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    admin.dispose()


@pytest.fixture(scope="session")
def postgres_engine() -> Iterator[Engine]:
    """Engine on a throwaway PostgreSQL database holding the domain schema."""
    url = _recreate_database(POSTGRES_TEST_DATABASE)
    pg_engine = create_engine(url)
    Base.metadata.create_all(pg_engine)
    try:
        yield pg_engine
    finally:
        pg_engine.dispose()
        _drop_database(POSTGRES_TEST_DATABASE)


@pytest.fixture
def postgres_session(postgres_engine: Engine) -> Iterator[Session]:
    """Session whose work is rolled back, so tests stay independent.

    The session joins an outer transaction on a dedicated connection; a test may
    call ``commit()`` freely because that only releases a savepoint.
    """
    connection = postgres_engine.connect()
    transaction = connection.begin()
    db_session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield db_session
    finally:
        db_session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def postgres_migration_url() -> Iterator[URL]:
    """URL of an empty PostgreSQL database for exercising Alembic end to end."""
    url = _recreate_database(POSTGRES_MIGRATION_DATABASE)
    try:
        yield url
    finally:
        _drop_database(POSTGRES_MIGRATION_DATABASE)
