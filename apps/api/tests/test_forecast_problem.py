from retailops_api.forecasting.problem import WEEKLY_CATEGORY_STORE_DEMAND


def test_the_first_problem_is_weekly_category_demand_per_store() -> None:
    problem = WEEKLY_CATEGORY_STORE_DEMAND

    assert problem.id == "weekly_category_store_demand"
    assert problem.target == "units_sold"
    assert problem.grain == ("store_code", "category_code", "period_start")
    assert problem.frequency == "weekly-monday"
    assert problem.horizon_periods == 4
    assert problem.history_periods is None
    assert "sum" in problem.aggregation
    assert "zero-fill" in problem.missing_periods
