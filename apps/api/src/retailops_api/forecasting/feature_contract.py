"""Features that may be used at prediction time, and which ones leak.

A feature is available at prediction time when it can be computed from
information known at the origin: the calendar of the target week, identifiers,
and history on or before the cutoff. Contemporaneous price, discount,
promotion and stock of the *target* week are not known unless a separate plan
is supplied; reading them from that week's sales is leakage.

Lag and rolling features must be built from weeks strictly before the target
week and on or before the cutoff. Rolling statistics are shifted (the target
week is never inside the window) so a row cannot see its own label.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from retailops_api.forecasting.coerce import as_int, as_int_tuple, as_str_tuple

DEFAULT_LAGS = (1, 2, 4, 8)
DEFAULT_ROLLING_WINDOW = 4
DEFAULT_ROLLING_STATS = ("mean", "median", "std")
DEFAULT_MIN_HISTORY_WEEKS = 8
ALLOWED_ROLLING_STATS = frozenset(DEFAULT_ROLLING_STATS)

CALENDAR_FEATURE_NAMES = (
    "iso_week",
    "iso_year",
    "month",
    "week_of_month",
    "is_month_start_week",
    "is_month_end_week",
    "is_mid_month_week",
    "christmas_days",
    "new_year_days",
    "buen_fin_days",
    "holiday_days",
    "mean_demand_multiplier",
)

COMMERCIAL_LAG_NAMES = (
    "price_lag_1",
    "discount_lag_1",
    "promo_rate_lag_1",
    "stock_lag_1",
    "stockout_rate_lag_1",
)

IDENTIFIER_FEATURE_NAMES = (
    "store_id",
    "category_id",
    "store_region_id",
    "store_type_id",
)

CATEGORICAL_FEATURE_NAMES = IDENTIFIER_FEATURE_NAMES


class FeatureFamily(StrEnum):
    horizon = "horizon"
    calendar = "calendar"
    lag = "lag"
    rolling = "rolling"
    price = "price"
    discount = "discount"
    promotion = "promotion"
    stock = "stock"
    identifier = "identifier"


class LeakageRisk(StrEnum):
    none = "none"
    historical_only = "historical_only"
    leaky_if_contemporaneous = "leaky_if_contemporaneous"


@dataclass(frozen=True)
class FeatureSpec:
    """One named input and whether it is safe to compute at an origin."""

    name: str
    family: FeatureFamily
    available_at_prediction_time: bool
    leakage_risk: LeakageRisk
    description: str

    def to_dict(self) -> dict[str, str | bool]:
        return {
            "name": self.name,
            "family": self.family.value,
            "available_at_prediction_time": self.available_at_prediction_time,
            "leakage_risk": self.leakage_risk.value,
            "description": self.description,
        }


FEATURE_CONTRACT: tuple[FeatureSpec, ...] = (
    FeatureSpec(
        name="horizon_step",
        family=FeatureFamily.horizon,
        available_at_prediction_time=True,
        leakage_risk=LeakageRisk.none,
        description="Weeks from the origin to the target week (1 = next week).",
    ),
    FeatureSpec(
        name="iso_week",
        family=FeatureFamily.calendar,
        available_at_prediction_time=True,
        leakage_risk=LeakageRisk.none,
        description="ISO week number of the target Monday (1-53).",
    ),
    FeatureSpec(
        name="iso_year",
        family=FeatureFamily.calendar,
        available_at_prediction_time=True,
        leakage_risk=LeakageRisk.none,
        description="ISO year of the target Monday.",
    ),
    FeatureSpec(
        name="month",
        family=FeatureFamily.calendar,
        available_at_prediction_time=True,
        leakage_risk=LeakageRisk.none,
        description="Calendar month of the target Monday.",
    ),
    FeatureSpec(
        name="week_of_month",
        family=FeatureFamily.calendar,
        available_at_prediction_time=True,
        leakage_risk=LeakageRisk.none,
        description="1-based week index of the target Monday within its calendar month.",
    ),
    FeatureSpec(
        name="is_month_start_week",
        family=FeatureFamily.calendar,
        available_at_prediction_time=True,
        leakage_risk=LeakageRisk.none,
        description="1 when the ISO week contains the first day of a month.",
    ),
    FeatureSpec(
        name="is_month_end_week",
        family=FeatureFamily.calendar,
        available_at_prediction_time=True,
        leakage_risk=LeakageRisk.none,
        description="1 when the ISO week contains the last day of a month.",
    ),
    FeatureSpec(
        name="is_mid_month_week",
        family=FeatureFamily.calendar,
        available_at_prediction_time=True,
        leakage_risk=LeakageRisk.none,
        description="1 when the ISO week contains the 15th.",
    ),
    FeatureSpec(
        name="christmas_days",
        family=FeatureFamily.calendar,
        available_at_prediction_time=True,
        leakage_risk=LeakageRisk.none,
        description="Count of days in 20-25 December inside the target week.",
    ),
    FeatureSpec(
        name="new_year_days",
        family=FeatureFamily.calendar,
        available_at_prediction_time=True,
        leakage_risk=LeakageRisk.none,
        description="Count of 1-2 January days inside the target week.",
    ),
    FeatureSpec(
        name="buen_fin_days",
        family=FeatureFamily.calendar,
        available_at_prediction_time=True,
        leakage_risk=LeakageRisk.none,
        description="Count of Buen Fin days (Friday-Monday before 20 November) in the week.",
    ),
    FeatureSpec(
        name="holiday_days",
        family=FeatureFamily.calendar,
        available_at_prediction_time=True,
        leakage_risk=LeakageRisk.none,
        description="Count of configured holiday dates inside the target week.",
    ),
    FeatureSpec(
        name="mean_demand_multiplier",
        family=FeatureFamily.calendar,
        available_at_prediction_time=True,
        leakage_risk=LeakageRisk.none,
        description="Mean of the seven daily calendar demand multipliers.",
    ),
    FeatureSpec(
        name="lag_k",
        family=FeatureFamily.lag,
        available_at_prediction_time=True,
        leakage_risk=LeakageRisk.historical_only,
        description=(
            "Target at the week k steps before the target week, only if that "
            "week is on or before the cutoff. Missing lookbacks are 0."
        ),
    ),
    FeatureSpec(
        name="roll_*_n",
        family=FeatureFamily.rolling,
        available_at_prediction_time=True,
        leakage_risk=LeakageRisk.historical_only,
        description=(
            "Mean, median or std of the last n weeks strictly before the "
            "target and on or before the cutoff. The target week is shifted "
            "out of the window. Optional min/max use the same window."
        ),
    ),
    FeatureSpec(
        name="price_lag_1",
        family=FeatureFamily.price,
        available_at_prediction_time=True,
        leakage_risk=LeakageRisk.historical_only,
        description=(
            "Units-weighted average selling price of the last observed week "
            "on or before the cutoff. Not the target week's own price."
        ),
    ),
    FeatureSpec(
        name="discount_lag_1",
        family=FeatureFamily.discount,
        available_at_prediction_time=True,
        leakage_risk=LeakageRisk.historical_only,
        description="Units-weighted average discount of the last week on or before the cutoff.",
    ),
    FeatureSpec(
        name="promo_rate_lag_1",
        family=FeatureFamily.promotion,
        available_at_prediction_time=True,
        leakage_risk=LeakageRisk.historical_only,
        description=(
            "Share of store-SKU days on promotion in the last week on or before the cutoff."
        ),
    ),
    FeatureSpec(
        name="stock_lag_1",
        family=FeatureFamily.stock,
        available_at_prediction_time=True,
        leakage_risk=LeakageRisk.historical_only,
        description="Average closing stock of the last week on or before the cutoff.",
    ),
    FeatureSpec(
        name="stockout_rate_lag_1",
        family=FeatureFamily.stock,
        available_at_prediction_time=True,
        leakage_risk=LeakageRisk.historical_only,
        description=(
            "Share of store-SKU days with zero stock in the last week on or before the cutoff."
        ),
    ),
    FeatureSpec(
        name="store_id",
        family=FeatureFamily.identifier,
        available_at_prediction_time=True,
        leakage_risk=LeakageRisk.none,
        description="Integer encoding of store_code fitted on the training catalog.",
    ),
    FeatureSpec(
        name="category_id",
        family=FeatureFamily.identifier,
        available_at_prediction_time=True,
        leakage_risk=LeakageRisk.none,
        description="Integer encoding of category_code fitted on the training catalog.",
    ),
    FeatureSpec(
        name="store_region_id",
        family=FeatureFamily.identifier,
        available_at_prediction_time=True,
        leakage_risk=LeakageRisk.none,
        description="Integer encoding of the store's region.",
    ),
    FeatureSpec(
        name="store_type_id",
        family=FeatureFamily.identifier,
        available_at_prediction_time=True,
        leakage_risk=LeakageRisk.none,
        description="Integer encoding of the store's type.",
    ),
    FeatureSpec(
        name="avg_price",
        family=FeatureFamily.price,
        available_at_prediction_time=False,
        leakage_risk=LeakageRisk.leaky_if_contemporaneous,
        description=(
            "Units-weighted average selling price of the target week itself. "
            "Excluded from the default feature set: that week's sales are not "
            "known at the origin."
        ),
    ),
    FeatureSpec(
        name="avg_discount",
        family=FeatureFamily.discount,
        available_at_prediction_time=False,
        leakage_risk=LeakageRisk.leaky_if_contemporaneous,
        description="Target-week discount. Excluded; contemporaneous sales leak the label's week.",
    ),
    FeatureSpec(
        name="promo_rate",
        family=FeatureFamily.promotion,
        available_at_prediction_time=False,
        leakage_risk=LeakageRisk.leaky_if_contemporaneous,
        description=(
            "Target-week promotion rate from sales. Excluded unless a promo calendar is supplied."
        ),
    ),
    FeatureSpec(
        name="avg_stock",
        family=FeatureFamily.stock,
        available_at_prediction_time=False,
        leakage_risk=LeakageRisk.leaky_if_contemporaneous,
        description="Target-week closing stock. Excluded; future stock is not known at the origin.",
    ),
    FeatureSpec(
        name="stockout_rate",
        family=FeatureFamily.stock,
        available_at_prediction_time=False,
        leakage_risk=LeakageRisk.leaky_if_contemporaneous,
        description="Target-week stockout rate. Excluded for the same reason as avg_stock.",
    ),
)


@dataclass(frozen=True)
class FeatureConfig:
    """Which historical lags, rolling window and families to materialise."""

    lags: tuple[int, ...] = DEFAULT_LAGS
    rolling_window: int = DEFAULT_ROLLING_WINDOW
    rolling_stats: tuple[str, ...] = DEFAULT_ROLLING_STATS
    rolling_min_max: bool = True
    include_calendar: bool = True
    include_commercial_lags: bool = True
    include_identifiers: bool = True
    holidays: tuple[date, ...] = ()
    min_history_weeks: int = DEFAULT_MIN_HISTORY_WEEKS

    def __post_init__(self) -> None:
        if any(lag < 1 for lag in self.lags):
            raise ValueError("every lag must be at least 1")
        if self.rolling_window < 1:
            raise ValueError("rolling_window must be at least 1")
        unknown = [stat for stat in self.rolling_stats if stat not in ALLOWED_ROLLING_STATS]
        if unknown:
            raise ValueError(f"unsupported rolling stats: {unknown}")
        if self.min_history_weeks < 1:
            raise ValueError("min_history_weeks must be at least 1")

    def feature_names(self) -> tuple[str, ...]:
        names = ["horizon_step"]
        if self.include_calendar:
            names.extend(CALENDAR_FEATURE_NAMES)
        names.extend(f"lag_{lag}" for lag in self.lags)
        for stat in self.rolling_stats:
            names.append(f"roll_{stat}_{self.rolling_window}")
        if self.rolling_min_max:
            names.append(f"roll_min_{self.rolling_window}")
            names.append(f"roll_max_{self.rolling_window}")
        if self.include_commercial_lags:
            names.extend(COMMERCIAL_LAG_NAMES)
        if self.include_identifiers:
            names.extend(IDENTIFIER_FEATURE_NAMES)
        return tuple(names)

    def to_dict(self) -> dict[str, object]:
        return {
            "lags": list(self.lags),
            "rolling_window": self.rolling_window,
            "rolling_stats": list(self.rolling_stats),
            "rolling_min_max": self.rolling_min_max,
            "include_calendar": self.include_calendar,
            "include_commercial_lags": self.include_commercial_lags,
            "include_identifiers": self.include_identifiers,
            "holidays": [day.isoformat() for day in self.holidays],
            "min_history_weeks": self.min_history_weeks,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> FeatureConfig:
        holidays = tuple(
            date.fromisoformat(str(day)) for day in as_str_tuple(payload.get("holidays"), ())
        )
        return cls(
            lags=as_int_tuple(payload.get("lags"), DEFAULT_LAGS),
            rolling_window=as_int(payload.get("rolling_window"), DEFAULT_ROLLING_WINDOW),
            rolling_stats=as_str_tuple(payload.get("rolling_stats"), DEFAULT_ROLLING_STATS),
            rolling_min_max=bool(payload.get("rolling_min_max", True)),
            include_calendar=bool(payload.get("include_calendar", True)),
            include_commercial_lags=bool(payload.get("include_commercial_lags", True)),
            include_identifiers=bool(payload.get("include_identifiers", True)),
            holidays=holidays,
            min_history_weeks=as_int(payload.get("min_history_weeks"), DEFAULT_MIN_HISTORY_WEEKS),
        )


def contract_by_name() -> dict[str, FeatureSpec]:
    return {spec.name: spec for spec in FEATURE_CONTRACT}


def leaky_feature_names() -> tuple[str, ...]:
    return tuple(
        spec.name
        for spec in FEATURE_CONTRACT
        if spec.leakage_risk is LeakageRisk.leaky_if_contemporaneous
    )
