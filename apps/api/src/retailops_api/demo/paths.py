from dataclasses import dataclass
from pathlib import Path


def find_repo_root() -> Path:
    for candidate in (Path.cwd(), *Path.cwd().parents):
        if (candidate / "apps" / "api" / "pyproject.toml").exists():
            return candidate
    return Path.cwd()


def api_root() -> Path:
    return Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class DemoPaths:
    synthetic: Path
    forecasts: Path
    documents: Path
    reviews: Path
    registry: Path


def default_demo_paths(root: Path | None = None) -> DemoPaths:
    base = root or find_repo_root()
    return DemoPaths(
        synthetic=base / "data" / "synthetic",
        forecasts=base / "data" / "forecasts",
        documents=base / "data" / "documents",
        reviews=base / "data" / "reviews",
        registry=base / "artifacts" / "models",
    )
