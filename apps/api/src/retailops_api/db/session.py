from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from retailops_api.core.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for future domain models."""


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    return create_engine(
        settings.database_url,
        echo=settings.database_echo,
        pool_pre_ping=True,
        future=True,
    )


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    with get_session_factory()() as session:
        yield session


def check_database_connection() -> bool:
    """Return whether the configured database currently accepts connections."""
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        return False
    return True
