from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from retailops_api.domain.models import ForecastPrediction, ForecastRun
from retailops_api.forecasting.backtest import BacktestFold, BacktestResult
from retailops_api.forecasting.metrics import ForecastMetrics
from retailops_api.forecasting.models import ForecastPoint
from retailops_api.forecasting.persist import persist_backtest, persist_run

GENERATED = datetime(2026, 8, 30, 13, 32, tzinfo=UTC)


def test_persist_run_writes_the_run_and_its_points(session: Session) -> None:
    run = persist_run(
        session,
        model_id="naive",
        generated_at=GENERATED,
        cutoff=date(2025, 6, 2),
        horizon=2,
        problem_id="weekly_category_store_demand",
        predictions=(
            ForecastPoint("ST-001", "BEV-SOFT", date(2025, 6, 9), 1, 10.0, actual=9.0),
            ForecastPoint("ST-001", "BEV-SOFT", date(2025, 6, 16), 2, 10.0, actual=None),
        ),
        run_metadata={"window": 4},
    )

    assert session.get(ForecastRun, run.id) is not None
    rows = session.query(ForecastPrediction).order_by(ForecastPrediction.step).all()
    assert len(rows) == 2
    assert rows[0].actual == 9.0
    assert rows[1].actual is None
    assert rows[0].forecast_run_id == run.id


def test_persist_backtest_groups_folds_by_a_shared_id(session: Session) -> None:
    metrics = ForecastMetrics(mae=1.0, rmse=1.0, wape=0.5, bias=0.0)
    result = BacktestResult(
        model_id="naive",
        horizon=1,
        folds=(
            BacktestFold(
                cutoff=date(2025, 6, 2),
                horizon=1,
                model_id="naive",
                metrics=metrics,
                predictions=(ForecastPoint("ST-001", "BEV-SOFT", date(2025, 6, 9), 1, 4.0, 5.0),),
            ),
            BacktestFold(
                cutoff=date(2025, 6, 9),
                horizon=1,
                model_id="naive",
                metrics=metrics,
                predictions=(ForecastPoint("ST-001", "BEV-SOFT", date(2025, 6, 16), 1, 5.0, 6.0),),
            ),
        ),
        overall=metrics,
    )

    runs = persist_backtest(
        session,
        result,
        generated_at=GENERATED,
        problem_id="weekly_category_store_demand",
        backtest_id="bt-1",
    )

    assert len(runs) == 2
    metadata = [run.run_metadata or {} for run in runs]
    assert {row["backtest_id"] for row in metadata} == {"bt-1"}
    assert [row["fold_index"] for row in metadata] == [0, 1]
    assert session.query(ForecastPrediction).count() == 2
