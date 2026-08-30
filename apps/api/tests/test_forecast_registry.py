from pathlib import Path

import pytest

from retailops_api.forecasting.registry import (
    ApprovalStatus,
    LocalModelRegistry,
    RegistryError,
)


def _artifact(path: Path, label: str) -> Path:
    path.mkdir(parents=True)
    (path / "marker.txt").write_text(label, encoding="utf-8")
    return path


def test_register_assigns_monotonic_versions(tmp_path: Path) -> None:
    registry = LocalModelRegistry(tmp_path)
    first = registry.register("category-forecast", _artifact(tmp_path / "a", "one"))
    second = registry.register("category-forecast", _artifact(tmp_path / "b", "two"))

    assert first.version == "v001"
    assert second.version == "v002"
    assert first.status is ApprovalStatus.candidate
    assert (first.artifact_path / "marker.txt").read_text(encoding="utf-8") == "one"
    assert [item.version for item in registry.list_versions("category-forecast")] == [
        "v001",
        "v002",
    ]
    assert registry.get_version("category-forecast", "v002").version == "v002"


def test_champion_retrieval_and_approval_handoff(tmp_path: Path) -> None:
    registry = LocalModelRegistry(tmp_path)
    first = registry.register("category-forecast", _artifact(tmp_path / "a", "one"))
    second = registry.register("category-forecast", _artifact(tmp_path / "b", "two"))

    assert registry.get_champion("category-forecast") is None

    registry.update_approval("category-forecast", first.version, ApprovalStatus.champion)
    champion = registry.get_champion("category-forecast")
    assert champion is not None
    assert champion.version == "v001"

    registry.update_approval("category-forecast", second.version, ApprovalStatus.champion)
    champion = registry.get_champion("category-forecast")
    assert champion is not None
    assert champion.version == "v002"
    assert registry.get_version("category-forecast", "v001").status is ApprovalStatus.approved


def test_unknown_version_is_an_error(tmp_path: Path) -> None:
    registry = LocalModelRegistry(tmp_path)
    registry.register("category-forecast", _artifact(tmp_path / "a", "one"))

    with pytest.raises(RegistryError, match="unknown version"):
        registry.get_version("category-forecast", "v099")
