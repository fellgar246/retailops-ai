"""Shared helpers for job tests."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from types import TracebackType
from typing import cast

from sqlalchemy.orm import Session


class _BorrowedSession(AbstractContextManager["Session"]):
    """Hand the worker the test's session without letting it close it.

    A worker opens and closes a session per job. Here the test needs to keep
    reading the same one afterwards, so exiting is a no-op.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def __call__(self) -> _BorrowedSession:
        return self

    def __enter__(self) -> Session:
        return self._session

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None


def borrowed_session_factory(session: Session) -> Callable[[], Session]:
    """A session factory the worker can use that shares the test's session."""

    return cast(Callable[[], Session], _BorrowedSession(session))
