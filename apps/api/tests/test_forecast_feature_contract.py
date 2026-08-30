from retailops_api.forecasting.feature_contract import (
    FEATURE_CONTRACT,
    FeatureConfig,
    FeatureFamily,
    LeakageRisk,
    leaky_feature_names,
)


def test_every_candidate_family_is_named_on_the_contract() -> None:
    families = {spec.family for spec in FEATURE_CONTRACT}
    assert families == set(FeatureFamily)


def test_contemporaneous_commercial_features_are_marked_leaky() -> None:
    leaky = leaky_feature_names()
    assert "avg_price" in leaky
    assert "avg_discount" in leaky
    assert "promo_rate" in leaky
    assert "avg_stock" in leaky
    assert "stockout_rate" in leaky
    for spec in FEATURE_CONTRACT:
        if spec.name in leaky:
            assert spec.available_at_prediction_time is False
            assert spec.leakage_risk is LeakageRisk.leaky_if_contemporaneous


def test_default_feature_names_exclude_leaky_contemporaneous_columns() -> None:
    names = FeatureConfig().feature_names()

    assert "horizon_step" in names
    assert "lag_1" in names
    assert "roll_mean_4" in names
    assert "roll_min_4" in names
    assert "price_lag_1" in names
    assert "store_id" in names
    for name in leaky_feature_names():
        assert name not in names


def test_lags_and_rolling_are_historical_only() -> None:
    by_name = {spec.name: spec for spec in FEATURE_CONTRACT}
    assert by_name["lag_k"].leakage_risk is LeakageRisk.historical_only
    assert by_name["roll_*_n"].leakage_risk is LeakageRisk.historical_only
    assert by_name["iso_week"].leakage_risk is LeakageRisk.none
    assert by_name["iso_week"].available_at_prediction_time is True


def test_feature_config_round_trips_through_a_dict() -> None:
    config = FeatureConfig(lags=(1, 4), rolling_min_max=False, min_history_weeks=6)
    restored = FeatureConfig.from_dict(config.to_dict())

    assert restored == config
    assert "roll_min_4" not in restored.feature_names()
