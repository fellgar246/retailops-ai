"""Generator configuration: presets, overrides and rejected values."""

from datetime import date

import pytest
from pydantic import ValidationError

from retailops_api.synthetic.config import GeneratorConfig, ScalePreset


def test_tiny_preset_is_small_enough_for_tests() -> None:
    config = GeneratorConfig.from_preset(ScalePreset.tiny)

    assert config.store_count == 2
    assert config.product_count == 8
    assert config.start_date <= config.end_date
    assert (config.end_date - config.start_date).days < 40


def test_every_named_scale_builds() -> None:
    for preset in ScalePreset:
        config = GeneratorConfig.from_preset(preset)
        assert config.preset == preset
        assert config.seed == 42


def test_overrides_replace_preset_fields() -> None:
    config = GeneratorConfig.from_preset("tiny", seed=7, store_count=3)

    assert config.seed == 7
    assert config.store_count == 3
    assert config.product_count == 8


def test_an_inverted_date_range_is_rejected() -> None:
    with pytest.raises(ValidationError, match="end_date"):
        GeneratorConfig.from_preset("tiny", start_date=date(2026, 4, 1), end_date=date(2026, 3, 1))


@pytest.mark.parametrize("field", ["promotion_probability", "stockout_probability"])
def test_probabilities_must_be_between_zero_and_one(field: str) -> None:
    with pytest.raises(ValidationError):
        GeneratorConfig.from_preset("tiny", **{field: 1.5})


def test_catalog_and_demand_use_separate_streams() -> None:
    config = GeneratorConfig.from_preset("tiny")

    assert config.catalog_seed != config.demand_seed
