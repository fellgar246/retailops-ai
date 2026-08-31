"""Shared bootstrap helper for local dataset and contract tests."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from retailops_api.demo.bootstrap import DemoReport, bootstrap_demo
from retailops_api.demo.paths import DemoPaths


def demo_paths(tmp_path: Path) -> DemoPaths:
    return DemoPaths(
        synthetic=tmp_path / "synthetic",
        forecasts=tmp_path / "forecasts",
        documents=tmp_path / "documents",
        reviews=tmp_path / "reviews",
        registry=tmp_path / "registry",
    )


def load_demo(session: Session, tmp_path: Path, *, preset: str = "tiny") -> DemoReport:
    return bootstrap_demo(session, paths=demo_paths(tmp_path), preset=preset)
