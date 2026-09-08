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
from retailops_api.core.config import Settings, get_settings
from retailops_api.domain.models import Base
from retailops_api.identity.local import LocalIdentityVerifier
from retailops_api.identity.types import Principal, Role
from retailops_api.main import create_app

#: Long enough for HMAC-SHA256; the value itself is meaningless.
TEST_IDENTITY_SECRET = "retailops-test-identity-secret-value"

#: Scratch database for the PostgreSQL integration tests. Created and dropped by
#: the fixtures below so the developer's own database is never touched.
POSTGRES_TEST_DATABASE = "retailops_test"

#: Separate database again for migration tests, which drop every table.
POSTGRES_MIGRATION_DATABASE = "retailops_migration_test"


def _application_env_names() -> set[str]:
    """Every environment variable the settings model would read."""

    names: set[str] = set()
    for name, field in Settings.model_fields.items():
        names.add(name.upper())
        alias = field.validation_alias
        choices = getattr(alias, "choices", None)
        if choices:
            names.update(str(choice).upper() for choice in choices)
        elif isinstance(alias, str):
            names.add(alias.upper())
    return names


@pytest.fixture(autouse=True, scope="session")
def isolated_settings() -> Iterator[None]:
    """Keep the suite independent of the machine it runs on.

    Settings normally load a developer's environment file. Reading it here
    would make adapter selection depend on local configuration, so the file and
    any matching variables are taken out of scope for the whole session.
    """

    original_env_file = Settings.model_config.get("env_file")
    Settings.model_config["env_file"] = None

    # The database URL still comes from the environment so the PostgreSQL
    # integration tests can reach a server the developer chose.
    preserved = {"DATABASE_URL"}
    removed = {
        name: os.environ.pop(name)
        for name in _application_env_names() - preserved
        if name in os.environ
    }
    get_settings.cache_clear()
    try:
        yield
    finally:
        os.environ.update(removed)
        Settings.model_config["env_file"] = original_env_file
        get_settings.cache_clear()


@pytest.fixture
def settings() -> Settings:
    return Settings(
        environment="test",
        auth_provider="local",
        auth_local_secret=TEST_IDENTITY_SECRET,
    )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


# --------------------------------------------------------------------------- #
# Identity: the suite signs its own development tokens
# --------------------------------------------------------------------------- #


@pytest.fixture
def verifier() -> LocalIdentityVerifier:
    return LocalIdentityVerifier(TEST_IDENTITY_SECRET)


@pytest.fixture
def reviewer() -> Principal:
    return Principal(
        subject="test-reviewer",
        display_name="Test Reviewer",
        email="reviewer@example.test",
        roles=frozenset({Role.reviewer}),
    )


@pytest.fixture
def viewer() -> Principal:
    return Principal(
        subject="test-viewer",
        display_name="Test Viewer",
        email="viewer@example.test",
        roles=frozenset({Role.viewer}),
    )


def _token(verifier: LocalIdentityVerifier, principal: Principal) -> str:
    return verifier.issue(
        principal.subject,
        display_name=principal.display_name,
        email=principal.email,
        roles=set(principal.roles),
    )


@pytest.fixture
def reviewer_token(verifier: LocalIdentityVerifier, reviewer: Principal) -> str:
    return _token(verifier, reviewer)


@pytest.fixture
def viewer_token(verifier: LocalIdentityVerifier, viewer: Principal) -> str:
    return _token(verifier, viewer)


def _bound_client(app: FastAPI, session: Session, token: str | None) -> Iterator[TestClient]:
    def _override() -> Iterator[Session]:
        yield session
        session.commit()

    app.dependency_overrides[get_db] = _override
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    with TestClient(app, headers=headers) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def api_client(app: FastAPI, session: Session, reviewer_token: str) -> Iterator[TestClient]:
    """Authenticated as a reviewer, which is what most endpoints need."""

    yield from _bound_client(app, session, reviewer_token)


@pytest.fixture
def viewer_client(app: FastAPI, session: Session, viewer_token: str) -> Iterator[TestClient]:
    yield from _bound_client(app, session, viewer_token)


@pytest.fixture
def anonymous_client(app: FastAPI, session: Session) -> Iterator[TestClient]:
    yield from _bound_client(app, session, None)


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
