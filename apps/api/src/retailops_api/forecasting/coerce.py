"""Narrow JSON-ish values before they enter frozen configs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence


def as_int(value: object, default: int) -> int:
    chosen = default if value is None else value
    if isinstance(chosen, bool) or not isinstance(chosen, int | float | str):
        raise TypeError(f"expected an integer, got {type(chosen)}")
    return int(chosen)


def as_float(value: object, default: float | None = None) -> float:
    chosen = default if value is None else value
    if chosen is None:
        raise TypeError("expected a number")
    if isinstance(chosen, bool) or not isinstance(chosen, int | float | str):
        raise TypeError(f"expected a number, got {type(chosen)}")
    return float(chosen)


def as_str_tuple(value: object, default: Sequence[object]) -> tuple[str, ...]:
    chosen = default if value is None else value
    if not isinstance(chosen, list | tuple):
        raise TypeError(f"expected a sequence, got {type(chosen)}")
    return tuple(str(item) for item in chosen)


def as_int_tuple(value: object, default: Sequence[object]) -> tuple[int, ...]:
    chosen = default if value is None else value
    if not isinstance(chosen, list | tuple):
        raise TypeError(f"expected a sequence, got {type(chosen)}")
    return tuple(as_int(item, 0) for item in chosen)


def as_mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise TypeError(f"expected a mapping, got {type(value)}")
    return {str(key): item for key, item in value.items()}
