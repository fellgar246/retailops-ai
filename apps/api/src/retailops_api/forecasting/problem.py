"""The first forecasting problem: weekly category demand per store.

Target
    Daily ``units_sold``, summed.

Grain
    One row per ``(store_code, category_code, period_start)``.
    ``category_code`` is the product's assigned category (typically a leaf).
    Parent categories are not rolled up.

Frequency
    ISO-8601 weeks that start on Monday. ``period_start`` is that Monday.

Horizon
    Four weeks ahead of the origin.

History window
    Every complete ISO week in the source sales history. A week is complete
    when Monday through Sunday all fall inside the history's date span.
    Incomplete edge weeks are dropped so a partial week cannot bias the target.

Aggregation
    Sum of daily ``units_sold`` across every product that belongs to the
    category, for that store, during the week.

Missing periods
    A store-category pair that has no sales rows in a complete week is stored
    as target ``0``. The panel is balanced: every store in the catalog is
    crossed with every category that has at least one product.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ForecastProblem:
    """What is predicted, at what grain, how far ahead, and how it is built."""

    id: str
    name: str
    target: str
    grain: tuple[str, ...]
    frequency: str
    horizon_periods: int
    history_periods: int | None
    aggregation: str
    missing_periods: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


WEEKLY_CATEGORY_STORE_DEMAND = ForecastProblem(
    id="weekly_category_store_demand",
    name="Weekly category demand per store",
    target="units_sold",
    grain=("store_code", "category_code", "period_start"),
    frequency="weekly-monday",
    horizon_periods=4,
    history_periods=None,
    aggregation="sum of daily units_sold across products in the category",
    missing_periods="zero-fill every complete ISO week in the panel",
)

DEFAULT_HORIZON_WEEKS = WEEKLY_CATEGORY_STORE_DEMAND.horizon_periods
DEFAULT_SEASONAL_LAG = 52
DEFAULT_MOVING_AVERAGE_WINDOW = 4
DEFAULT_MIN_TRAIN_PERIODS = 12
DEFAULT_STEP_WEEKS = 1
DEFAULT_VALIDATION_PERIODS = 4
DEFAULT_TEST_PERIODS = 8
