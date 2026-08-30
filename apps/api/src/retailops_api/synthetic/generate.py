"""Assemble a complete synthetic dataset from a generator config."""

from retailops_api.dataset.contract import Dataset
from retailops_api.synthetic.calendar import build_calendar
from retailops_api.synthetic.catalog import generate_catalog
from retailops_api.synthetic.config import GeneratorConfig
from retailops_api.synthetic.demand import generate_sales


def generate_dataset(config: GeneratorConfig) -> Dataset:
    """Generate catalog, calendar and sales history for ``config``.

    The result is deterministic: the same config always yields the same rows.
    """
    artifacts = generate_catalog(config)
    calendar = build_calendar(config)
    sales = generate_sales(config, artifacts, calendar)
    return Dataset(catalog=artifacts.catalog, sales=sales, calendar=calendar)
