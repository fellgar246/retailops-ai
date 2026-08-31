from pathlib import Path

import pytest

from retailops_api.forecasting.registry import ApprovalStatus, RegistryError
from retailops_api.forecasting.sagemaker_registry import SageMakerModelRegistry
from tests.aws_fakes import FakeSageMaker


def _artifact(path: Path, label: str) -> Path:
    path.mkdir(parents=True)
    (path / "marker.txt").write_text(label, encoding="utf-8")
    return path


def _registry() -> SageMakerModelRegistry:
    return SageMakerModelRegistry(
        FakeSageMaker(),
        model_package_group="category-forecast",
        artifact_bucket="retailops-dev-documents",
        artifact_prefix="models",
    )


def test_sagemaker_register_records_metadata_without_copying(tmp_path: Path) -> None:
    source = _artifact(tmp_path / "a", "one")
    registry = _registry()
    version = registry.register(
        "category-forecast",
        source,
        metrics={"wape": 0.12, "mae": 3.5},
        data_fingerprint="abc",
    )

    assert version.version == "v001"
    assert version.status is ApprovalStatus.candidate
    assert version.metrics == {"wape": 0.12, "mae": 3.5}
    assert version.data_fingerprint == "abc"
    assert version.artifact_path == source
    assert registry.declared_artifact_uri("category-forecast", version.version).startswith(
        "s3://retailops-dev-documents/models/"
    )
    assert (source / "marker.txt").read_text(encoding="utf-8") == "one"
    listed = registry.list_versions("category-forecast")
    assert [item.version for item in listed] == ["v001"]


def test_sagemaker_does_not_upload_or_create_a_sidecar_archive(tmp_path: Path) -> None:
    source = _artifact(tmp_path / "a", "one")
    client = FakeSageMaker()
    registry = SageMakerModelRegistry(
        client,
        model_package_group="category-forecast",
        artifact_bucket="retailops-dev-documents",
    )
    registry.register("category-forecast", source)
    assert list(tmp_path.iterdir()) == [source]
    created = client.packages[0]
    url = created["InferenceSpecification"]["Containers"][0]["ModelDataUrl"]
    assert url.startswith("s3://retailops-dev-documents/")
    assert not Path(url).exists()


def test_sagemaker_champion_handoff(tmp_path: Path) -> None:
    registry = _registry()
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


def test_sagemaker_unknown_version_is_an_error(tmp_path: Path) -> None:
    registry = _registry()
    registry.register("category-forecast", _artifact(tmp_path / "a", "one"))
    with pytest.raises(RegistryError, match="unknown version"):
        registry.get_version("category-forecast", "v099")
