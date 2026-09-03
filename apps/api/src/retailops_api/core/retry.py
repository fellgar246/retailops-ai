"""Bounded retry with exponential backoff and jitter.

Used by hosted adapters. Authorization, validation and schema errors are
not retried by callers; this helper only computes delays.
"""

from __future__ import annotations

import random
from dataclasses import dataclass


def compute_retry_delay(
    attempt: int,
    *,
    base_delay_seconds: float,
    max_delay_seconds: float,
    jitter: bool,
) -> float:
    if base_delay_seconds <= 0:
        return 0.0
    expo = base_delay_seconds * (2 ** max(0, attempt - 1))
    capped = max_delay_seconds if expo > max_delay_seconds else expo
    if not jitter:
        return capped
    return capped * random.random()


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay_seconds: float = 0.2
    max_delay_seconds: float = 2.0
    jitter: bool = True

    def delay_for(self, attempt: int) -> float:
        return compute_retry_delay(
            attempt,
            base_delay_seconds=self.base_delay_seconds,
            max_delay_seconds=self.max_delay_seconds,
            jitter=self.jitter,
        )
