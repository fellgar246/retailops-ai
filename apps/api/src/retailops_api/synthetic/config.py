"""Typed configuration for the synthetic retail generator."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ScalePreset(StrEnum):
    """Named generator scales.

    ``tiny`` is small enough for unit tests. ``development`` is a year of
    history at a handful of stores. ``benchmark`` is a two-year, larger-catalog
    run for local performance work.
    """

    tiny = "tiny"
    development = "development"
    benchmark = "benchmark"


class GeneratorConfig(BaseModel):
    """Knobs that fully determine a generated dataset.

    The same ``seed`` and remaining fields always produce the same catalog and
    the same sales history. Catalog draws and sales draws use separate streams
    derived from ``seed``, so changing the date range does not reshuffle the
    catalog.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    seed: int = 42
    start_date: date
    end_date: date
    store_count: int = Field(ge=1)
    product_count: int = Field(ge=1)
    supplier_count: int = Field(ge=1)
    category_count: int = Field(ge=1)
    promotion_probability: float = Field(ge=0.0, le=1.0)
    stockout_probability: float = Field(ge=0.0, le=1.0)
    holidays: tuple[date, ...] = ()
    preset: ScalePreset | None = None

    @model_validator(mode="after")
    def _date_range_is_ordered(self) -> Self:
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self

    @classmethod
    def from_preset(cls, preset: ScalePreset | str, **overrides: Any) -> Self:
        """Build a config from a named scale, optionally overriding fields."""
        name = ScalePreset(preset)
        values = {**_PRESETS[name], **overrides, "preset": name}
        return cls.model_validate(values)

    @property
    def catalog_seed(self) -> int:
        return self.seed

    @property
    def demand_seed(self) -> int:
        # A fixed offset keeps catalog and demand independent without hashing.
        return self.seed + 1_000_003


_PRESETS: dict[ScalePreset, dict[str, Any]] = {
    ScalePreset.tiny: {
        "seed": 42,
        "start_date": date(2026, 3, 1),
        "end_date": date(2026, 3, 21),
        "store_count": 2,
        "product_count": 8,
        "supplier_count": 3,
        "category_count": 5,
        "promotion_probability": 0.12,
        "stockout_probability": 0.06,
    },
    ScalePreset.development: {
        "seed": 42,
        "start_date": date(2025, 1, 1),
        "end_date": date(2025, 12, 31),
        "store_count": 5,
        "product_count": 20,
        "supplier_count": 4,
        "category_count": 10,
        "promotion_probability": 0.12,
        "stockout_probability": 0.05,
    },
    ScalePreset.benchmark: {
        "seed": 42,
        "start_date": date(2024, 1, 1),
        "end_date": date(2025, 12, 31),
        "store_count": 15,
        "product_count": 100,
        "supplier_count": 12,
        "category_count": 24,
        "promotion_probability": 0.15,
        "stockout_probability": 0.06,
    },
}
