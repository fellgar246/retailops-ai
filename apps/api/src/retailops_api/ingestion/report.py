"""Structured metadata for one ingestion run."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from retailops_api.dataset.validate import ValidationIssue
from retailops_api.ingestion.catalog import CatalogIngestionResult


@dataclass
class IngestionRunReport:
    """What one ingest did, in a form that can be printed or written as JSON."""

    source: str
    run_id: str
    started_at: datetime
    finished_at: datetime
    rows_read: int
    rows_accepted: int
    rows_rejected: int
    duplicate_count: int
    validation_errors: list[ValidationIssue] = field(default_factory=list)
    catalog: CatalogIngestionResult | None = None
    checksum: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "source": self.source,
            "run_id": self.run_id,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "rows_read": self.rows_read,
            "rows_accepted": self.rows_accepted,
            "rows_rejected": self.rows_rejected,
            "duplicate_count": self.duplicate_count,
            "validation_errors": [
                {
                    "table": issue.table,
                    "code": issue.code,
                    "message": issue.message,
                    "row_number": issue.row_number,
                    "field": issue.field,
                    "natural_key": issue.natural_key,
                }
                for issue in self.validation_errors
            ],
        }
        if self.catalog is not None:
            payload["catalog"] = self.catalog.to_dict()
        if self.checksum is not None:
            payload["checksum"] = self.checksum
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2) + "\n"

    def write_json(self, path: Path) -> None:
        path.write_text(self.to_json(), encoding="utf-8")

    def format_text(self) -> str:
        elapsed = self.finished_at - self.started_at
        lines = [
            f"source             {self.source}",
            f"run_id             {self.run_id}",
            f"started_at         {self.started_at.isoformat()}",
            f"finished_at        {self.finished_at.isoformat()}",
            f"elapsed            {elapsed.total_seconds():.2f}s",
            f"rows_read          {self.rows_read}",
            f"rows_accepted      {self.rows_accepted}",
            f"rows_rejected      {self.rows_rejected}",
            f"duplicate_count    {self.duplicate_count}",
        ]
        if self.checksum:
            lines.append(f"checksum           {self.checksum}")
        if self.catalog is not None:
            lines.append("")
            lines.append(self.catalog.format_report())
        if self.validation_errors:
            lines.append("")
            lines.append(f"validation_errors ({len(self.validation_errors)}):")
            for issue in self.validation_errors[:20]:
                where = issue.table
                if issue.row_number:
                    where += f" row {issue.row_number}"
                if issue.natural_key:
                    where += f" ({issue.natural_key})"
                lines.append(f"  {where}: {issue.message}")
            extra = len(self.validation_errors) - 20
            if extra > 0:
                lines.append(f"  … and {extra} more")
        return "\n".join(lines)
