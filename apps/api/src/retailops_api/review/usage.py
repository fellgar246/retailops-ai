"""Optional provider invocation metadata. Not part of ``ReviewResult``."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ProviderUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    latency_ms: float | None = None
    model_id: str | None = None
    region: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "latency_ms": self.latency_ms,
            "model_id": self.model_id,
            "region": self.region,
        }


def usage_from_converse(payload: object, *, model_id: str, region: str) -> ProviderUsage:
    mapping = payload if isinstance(payload, dict) else {}
    usage_raw = mapping.get("usage")
    metrics_raw = mapping.get("metrics")
    usage: dict[str, Any] = usage_raw if isinstance(usage_raw, dict) else {}
    metrics: dict[str, Any] = metrics_raw if isinstance(metrics_raw, dict) else {}
    input_tokens = _optional_int(usage.get("inputTokens"))
    output_tokens = _optional_int(usage.get("outputTokens"))
    total_tokens = _optional_int(usage.get("totalTokens"))
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens
    return ProviderUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        latency_ms=_optional_float(metrics.get("latencyMs")),
        model_id=model_id,
        region=region,
    )


def _optional_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
