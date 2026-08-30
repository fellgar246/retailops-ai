"""Supervised and inference feature frames with checksum and cutoff metadata."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from retailops_api.dataset.contract import Catalog
from retailops_api.forecasting.feature_contract import FeatureConfig
from retailops_api.forecasting.features import (
    IdentifierMaps,
    WeeklyObservables,
    fit_identifier_maps,
    observables_index,
    row_feature_values,
    series_index,
    target_index,
)
from retailops_api.forecasting.frame import ForecastEntity, ForecastFrame, require_periods
from retailops_api.forecasting.problem import ForecastProblem
from retailops_api.forecasting.weeks import add_weeks, iso_week_start


@dataclass(frozen=True)
class FeatureRow:
    """One origin/target pair: identifiers, the aligned vector and optional label."""

    store_code: str
    category_code: str
    period_start: date
    as_of: date
    horizon_step: int
    values: tuple[float, ...]
    target: float | None = None

    @property
    def entity(self) -> ForecastEntity:
        return ForecastEntity(self.store_code, self.category_code)


@dataclass(frozen=True)
class FeatureFrame:
    """Reproducible design matrix plus the metadata needed to rebuild it.

    ``dataset_checksum`` is the portable-dataset fingerprint. ``feature_names``
    is the column order of every ``values`` tuple. ``cutoff`` is the latest
    ``as_of`` used; no row may read history after that date. Holdout dates are
    recorded so a later run can reuse the same locked weeks.
    """

    problem: ForecastProblem
    config: FeatureConfig
    feature_names: tuple[str, ...]
    rows: tuple[FeatureRow, ...]
    dataset_checksum: str | None
    source: str
    cutoff: date
    train_end: date | None = None
    validation_end: date | None = None
    test_end: date | None = None
    identifier_maps: IdentifierMaps | None = None
    observables: tuple[WeeklyObservables, ...] = ()

    def __post_init__(self) -> None:
        expected = len(self.feature_names)
        for row in self.rows:
            if len(row.values) != expected:
                raise ValueError(
                    f"feature row {row.entity} {row.period_start} has "
                    f"{len(row.values)} values, expected {expected}"
                )
            if row.as_of > self.cutoff:
                raise ValueError(
                    f"feature row as_of {row.as_of.isoformat()} is after "
                    f"frame cutoff {self.cutoff.isoformat()}"
                )

    def to_dict(self) -> dict[str, object]:
        return {
            "problem": self.problem.to_dict(),
            "config": self.config.to_dict(),
            "feature_names": list(self.feature_names),
            "dataset_checksum": self.dataset_checksum,
            "source": self.source,
            "cutoff": self.cutoff.isoformat(),
            "train_end": self.train_end.isoformat() if self.train_end else None,
            "validation_end": self.validation_end.isoformat() if self.validation_end else None,
            "test_end": self.test_end.isoformat() if self.test_end else None,
            "row_count": len(self.rows),
        }


def build_supervised_frame(
    frame: ForecastFrame,
    *,
    config: FeatureConfig,
    train_end: date,
    horizon: int,
    observables: Sequence[WeeklyObservables] = (),
    catalog: Catalog | None = None,
    identifier_maps: IdentifierMaps | None = None,
    dataset_checksum: str | None = None,
    source: str = "",
    validation_end: date | None = None,
    test_end: date | None = None,
) -> FeatureFrame:
    """One row per entity, origin and horizon step whose target week is on or before ``train_end``.

    Origins start once ``min_history_weeks`` of history exist. Every target
    week is inside the training slice so validation labels cannot enter the
    fit. Features at origin ``as_of`` read only ``period_start <= as_of``.
    """
    if horizon < 1:
        raise ValueError("horizon must be at least 1")
    periods = require_periods(
        frame,
        config.min_history_weeks + horizon,
        what="a supervised feature frame",
    )
    last_origin = add_weeks(train_end, -horizon)
    origins = [
        week
        for index, week in enumerate(periods)
        if week <= last_origin and index >= config.min_history_weeks - 1
    ]
    maps = identifier_maps or fit_identifier_maps(
        frame, stores=catalog.stores if catalog is not None else ()
    )
    names = config.feature_names()
    rows = _rows_for_origins(
        frame,
        origins=origins,
        horizon=horizon,
        config=config,
        maps=maps,
        observables=observables,
        require_target=True,
        latest_target=train_end,
    )
    return FeatureFrame(
        problem=frame.problem,
        config=config,
        feature_names=names,
        rows=tuple(rows),
        dataset_checksum=dataset_checksum,
        source=source,
        cutoff=train_end,
        train_end=train_end,
        validation_end=validation_end,
        test_end=test_end,
        identifier_maps=maps,
        observables=tuple(observables),
    )


def build_inference_rows(
    frame: ForecastFrame,
    *,
    cutoff: date,
    horizon: int,
    config: FeatureConfig,
    identifier_maps: IdentifierMaps,
    observables: Sequence[WeeklyObservables] = (),
) -> tuple[FeatureRow, ...]:
    """Feature rows for the next ``horizon`` weeks after ``cutoff``."""
    if horizon < 1:
        raise ValueError("horizon must be at least 1")
    return tuple(
        _rows_for_origins(
            frame,
            origins=(iso_week_start(cutoff),),
            horizon=horizon,
            config=config,
            maps=identifier_maps,
            observables=observables,
            require_target=False,
            latest_target=None,
        )
    )


def _rows_for_origins(
    frame: ForecastFrame,
    *,
    origins: Sequence[date],
    horizon: int,
    config: FeatureConfig,
    maps: IdentifierMaps,
    observables: Sequence[WeeklyObservables],
    require_target: bool,
    latest_target: date | None,
) -> list[FeatureRow]:
    targets = target_index(frame)
    series = series_index(frame)
    commercial = observables_index(observables)
    rows: list[FeatureRow] = []
    for origin in origins:
        for entity in frame.entities():
            entity_series = series.get(entity, ())
            for step in range(1, horizon + 1):
                period = add_weeks(origin, step)
                if latest_target is not None and period > latest_target:
                    continue
                actual = targets.get((entity.store_code, entity.category_code, period))
                if require_target and actual is None:
                    continue
                values = row_feature_values(
                    entity=entity,
                    period_start=period,
                    cutoff=origin,
                    horizon_step=step,
                    config=config,
                    targets=targets,
                    series=entity_series,
                    commercial=commercial,
                    identifiers=maps,
                )
                rows.append(
                    FeatureRow(
                        store_code=entity.store_code,
                        category_code=entity.category_code,
                        period_start=period,
                        as_of=origin,
                        horizon_step=step,
                        values=values,
                        target=actual,
                    )
                )
    return rows
