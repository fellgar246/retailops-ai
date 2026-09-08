"""Fixed-window request limiting for state-changing endpoints.

The counter lives in the process, so a service running several workers allows
proportionally more traffic. That is acceptable here: the purpose is to stop a
single credential from hammering the decision endpoints, not to enforce a
precise global quota.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict


class RateLimitError(Exception):
    """The caller has used its allowance for the current window."""

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("rate limit exceeded")
        self.retry_after_seconds = retry_after_seconds


class FixedWindowLimiter:
    def __init__(self, *, limit: int, window_seconds: int) -> None:
        self._limit = limit
        self._window = window_seconds
        self._counts: dict[tuple[str, int], int] = defaultdict(int)
        self._lock = threading.Lock()

    def check(self, key: str, *, now: float | None = None) -> None:
        moment = time.monotonic() if now is None else now
        window = int(moment // self._window)
        with self._lock:
            # Only the current window is kept; earlier buckets are discarded so
            # the map cannot grow without bound.
            stale = [item for item in self._counts if item[1] != window]
            for item in stale:
                del self._counts[item]
            count = self._counts[(key, window)] + 1
            self._counts[(key, window)] = count
        if count > self._limit:
            elapsed = moment - (window * self._window)
            raise RateLimitError(max(1, int(self._window - elapsed)))
