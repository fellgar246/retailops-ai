"""One in-process pass that fills a local database for development and demos."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session

from retailops_api.demo.documents import ingest_demo_documents
from retailops_api.demo.forecasts import persist_demo_forecast
from retailops_api.demo.paths import DemoPaths, default_demo_paths
from retailops_api.demo.procurement import create_demo_procurement
from retailops_api.demo.reviews import open_demo_reviews
from retailops_api.demo.sales import seed_and_ingest_sales
from retailops_api.ingestion.catalog import CatalogIngestionResult
from retailops_api.ingestion.sales import SalesIngestionStats


@dataclass
class DemoReport:
    catalog: CatalogIngestionResult
    sales: SalesIngestionStats
    forecast_run_id: int | None
    document_ids: list[int] = field(default_factory=list)
    reconciliation_run_ids: list[int] = field(default_factory=list)
    review_case_ids: list[int] = field(default_factory=list)

    def format_text(self) -> str:
        lines = [
            f"catalog  created={self.catalog.created}  updated={self.catalog.updated}",
            (
                f"sales    read={self.sales.rows_read}  accepted={self.sales.rows_accepted}  "
                f"duplicates={self.sales.duplicate_count}  rejected={self.sales.rows_rejected}"
            ),
            f"forecast run={self.forecast_run_id or 'none'}",
            (
                f"documents {len(self.document_ids)}  "
                f"ids={','.join(str(item) for item in self.document_ids) or '-'}"
            ),
            (
                f"reconciliations {len(self.reconciliation_run_ids)}  "
                f"ids={','.join(str(item) for item in self.reconciliation_run_ids) or '-'}"
            ),
            (
                f"reviews {len(self.review_case_ids)}  "
                f"ids={','.join(str(item) for item in self.review_case_ids) or '-'}"
            ),
        ]
        return "\n".join(lines)


def bootstrap_demo(
    session: Session,
    *,
    paths: DemoPaths | None = None,
    preset: str = "tiny",
    documents_root: Path | None = None,
) -> DemoReport:
    """Seed, generate, ingest, persist a forecast, load sheets, match and open reviews.

    Does not commit. Does not apply migrations. The caller owns the transaction
    and the schema.
    """

    chosen = paths or default_demo_paths()
    storage = documents_root or chosen.documents
    dataset, catalog, sales = seed_and_ingest_sales(session, preset=preset, output=chosen.synthetic)
    forecast = persist_demo_forecast(session, dataset)
    documents = ingest_demo_documents(session, storage)
    reconciliations = create_demo_procurement(session)
    reviews = open_demo_reviews(session, documents, reconciliations)
    return DemoReport(
        catalog=catalog,
        sales=sales,
        forecast_run_id=None if forecast is None else forecast.id,
        document_ids=[item.document_id for item in documents],
        reconciliation_run_ids=[item.run_id for item in reconciliations],
        review_case_ids=[item.id for item in reviews],
    )
