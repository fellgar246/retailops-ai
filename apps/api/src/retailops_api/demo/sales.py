"""Seed the catalog, generate sales history and ingest it."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session

from retailops_api.dataset.contract import Dataset
from retailops_api.dataset.snapshot import write_dataset
from retailops_api.dataset.validate import assert_valid
from retailops_api.db.seed import seed_reference_data
from retailops_api.ingestion.catalog import CatalogIngestionResult, ingest_catalog
from retailops_api.ingestion.sales import SalesIngestionStats, ingest_sales
from retailops_api.synthetic.config import GeneratorConfig, ScalePreset
from retailops_api.synthetic.generate import generate_dataset

# Tiny's default span is too short for a four-week horizon. The local dataset
# uses this window so a forecast can be persisted without a year of history.
TINY_FORECAST_START = date(2025, 1, 6)
TINY_FORECAST_END = date(2025, 6, 29)


def generator_config(preset: str) -> GeneratorConfig:
    name = ScalePreset(preset)
    if name is ScalePreset.tiny:
        return GeneratorConfig.from_preset(
            name, start_date=TINY_FORECAST_START, end_date=TINY_FORECAST_END
        )
    return GeneratorConfig.from_preset(name)


def seed_and_ingest_sales(
    session: Session,
    *,
    preset: str,
    output: Path,
) -> tuple[Dataset, CatalogIngestionResult, SalesIngestionStats]:
    """Load the reference catalog, generate sales and upsert both."""

    catalog = seed_reference_data(session)
    dataset = generate_dataset(generator_config(preset))
    assert_valid(dataset)
    write_dataset(
        dataset,
        output,
        extra_manifest={"preset": preset, "purpose": "local-demo"},
    )
    catalog = ingest_catalog(session, dataset.catalog)
    sales = ingest_sales(session, dataset.sales)
    session.flush()
    return dataset, catalog, sales
