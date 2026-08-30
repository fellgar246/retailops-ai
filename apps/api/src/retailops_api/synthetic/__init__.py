"""Deterministic synthetic retail catalog and sales history."""

from retailops_api.synthetic.config import GeneratorConfig, ScalePreset
from retailops_api.synthetic.generate import generate_dataset

__all__ = [
    "GeneratorConfig",
    "ScalePreset",
    "generate_dataset",
]
