"""Calendar, lag, rolling and lagged commercial feature values.

Calendar features are deterministic from the target Monday and the holiday
list. Lag and rolling features read only weeks strictly before the target
and on or before the cutoff. Commercial measures (price, discount, promotion,
stock) are attached from a weekly observables panel and then lagged the same
way: the target week's own sales are never used.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from statistics import median, pstdev

from retailops_api.dataset.contract import Dataset, StoreRow
from retailops_api.forecasting.coerce import as_float
from retailops_api.forecasting.feature_contract import FeatureConfig
from retailops_api.forecasting.frame import ForecastEntity, ForecastFrame
from retailops_api.forecasting.weeks import add_weeks, iso_week_start
from retailops_api.synthetic.calendar import calendar_day


@dataclass(frozen=True)
class WeeklyObservables:
    """Store-category week of price, discount, promotion and stock.

    Built from daily sales. These values belong to the week they describe.
    Models may only consume them as lags (a week on or before the cutoff).
    """

    store_code: str
    category_code: str
    period_start: date
    avg_price: float
    avg_discount: float
    promo_rate: float
    avg_stock: float
    stockout_rate: float

    def to_dict(self) -> dict[str, object]:
        return {
            "store_code": self.store_code,
            "category_code": self.category_code,
            "period_start": self.period_start.isoformat(),
            "avg_price": self.avg_price,
            "avg_discount": self.avg_discount,
            "promo_rate": self.promo_rate,
            "avg_stock": self.avg_stock,
            "stockout_rate": self.stockout_rate,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> WeeklyObservables:
        return cls(
            store_code=str(payload["store_code"]),
            category_code=str(payload["category_code"]),
            period_start=date.fromisoformat(str(payload["period_start"])),
            avg_price=as_float(payload["avg_price"]),
            avg_discount=as_float(payload["avg_discount"]),
            promo_rate=as_float(payload["promo_rate"]),
            avg_stock=as_float(payload["avg_stock"]),
            stockout_rate=as_float(payload["stockout_rate"]),
        )


@dataclass(frozen=True)
class IdentifierMaps:
    """Integer encodings fitted on the training catalog (0 is unknown)."""

    store_id: dict[str, int]
    category_id: dict[str, int]
    store_region: dict[str, int]
    store_type: dict[str, int]

    def encode(self, store_code: str, category_code: str) -> tuple[float, float, float, float]:
        return (
            float(self.store_id.get(store_code, 0)),
            float(self.category_id.get(category_code, 0)),
            float(self.store_region.get(store_code, 0)),
            float(self.store_type.get(store_code, 0)),
        )

    def to_dict(self) -> dict[str, dict[str, int]]:
        return {
            "store_id": dict(self.store_id),
            "category_id": dict(self.category_id),
            "store_region": dict(self.store_region),
            "store_type": dict(self.store_type),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> IdentifierMaps:
        def _ints(key: str) -> dict[str, int]:
            raw = payload.get(key, {})
            if not isinstance(raw, dict):
                return {}
            return {str(name): int(value) for name, value in raw.items()}

        return cls(
            store_id=_ints("store_id"),
            category_id=_ints("category_id"),
            store_region=_ints("store_region"),
            store_type=_ints("store_type"),
        )


def weekly_calendar_features(
    monday: date,
    holidays: Iterable[date] = (),
) -> dict[str, float]:
    """Deterministic event and calendar flags for one ISO week.

    ``monday`` must be the Monday that starts the week. Holidays are the
    extra closure dates; Christmas, New Year and Buen Fin are derived from
    the date itself.
    """
    if monday != iso_week_start(monday):
        raise ValueError("period_start must be an ISO week Monday")

    holiday_set = tuple(holidays)
    days = [calendar_day(monday + timedelta(days=offset), holiday_set) for offset in range(7)]
    iso = monday.isocalendar()
    return {
        "iso_week": float(iso.week),
        "iso_year": float(iso.year),
        "month": float(monday.month),
        "week_of_month": float((monday.day - 1) // 7 + 1),
        "is_month_start_week": float(any(day.is_month_start for day in days)),
        "is_month_end_week": float(any(day.is_month_end for day in days)),
        "is_mid_month_week": float(any(day.is_mid_month for day in days)),
        "christmas_days": float(sum(1 for day in days if day.is_christmas)),
        "new_year_days": float(sum(1 for day in days if day.is_new_year)),
        "buen_fin_days": float(sum(1 for day in days if day.is_buen_fin)),
        "holiday_days": float(sum(1 for day in days if day.is_holiday)),
        "mean_demand_multiplier": round(sum(day.demand_multiplier for day in days) / 7.0, 6),
    }


def lag_value(
    index: dict[tuple[str, str, date], float],
    entity: ForecastEntity,
    *,
    period_start: date,
    lag: int,
    cutoff: date,
) -> float:
    """Target at ``period_start - lag`` weeks, or 0 when that week is unseen or after the cutoff."""
    if lag < 1:
        raise ValueError("lag must be at least 1")
    lookback = add_weeks(period_start, -lag)
    if lookback > cutoff:
        return 0.0
    return index.get((entity.store_code, entity.category_code, lookback), 0.0)


def rolling_values(
    series: Sequence[tuple[date, float]],
    *,
    period_start: date,
    cutoff: date,
    window: int,
    stats: Sequence[str],
    include_min_max: bool,
) -> dict[str, float]:
    """Shifted rolling statistics: the target week is never inside the window."""
    if window < 1:
        raise ValueError("window must be at least 1")
    eligible = [value for week, value in series if week < period_start and week <= cutoff]
    trailing = eligible[-window:]
    result: dict[str, float] = {}
    for stat in stats:
        result[f"roll_{stat}_{window}"] = _rolling_stat(trailing, stat)
    if include_min_max:
        result[f"roll_min_{window}"] = min(trailing) if trailing else 0.0
        result[f"roll_max_{window}"] = max(trailing) if trailing else 0.0
    return result


def last_observables(
    index: dict[tuple[str, str, date], WeeklyObservables],
    entity: ForecastEntity,
    *,
    cutoff: date,
    before: date,
) -> WeeklyObservables | None:
    """Latest observables with ``period_start <= cutoff`` and ``period_start < before``."""
    latest: date | None = None
    for store_code, category_code, week in index:
        if (
            store_code == entity.store_code
            and category_code == entity.category_code
            and week <= cutoff
            and week < before
            and (latest is None or week > latest)
        ):
            latest = week
    if latest is None:
        return None
    return index[(entity.store_code, entity.category_code, latest)]


def commercial_lag_values(
    index: dict[tuple[str, str, date], WeeklyObservables],
    entity: ForecastEntity,
    *,
    period_start: date,
    cutoff: date,
) -> dict[str, float]:
    observed = last_observables(index, entity, cutoff=cutoff, before=period_start)
    if observed is None:
        return {
            "price_lag_1": 0.0,
            "discount_lag_1": 0.0,
            "promo_rate_lag_1": 0.0,
            "stock_lag_1": 0.0,
            "stockout_rate_lag_1": 0.0,
        }
    return {
        "price_lag_1": observed.avg_price,
        "discount_lag_1": observed.avg_discount,
        "promo_rate_lag_1": observed.promo_rate,
        "stock_lag_1": observed.avg_stock,
        "stockout_rate_lag_1": observed.stockout_rate,
    }


def target_index(frame: ForecastFrame) -> dict[tuple[str, str, date], float]:
    return {(row.store_code, row.category_code, row.period_start): row.target for row in frame.rows}


def series_index(frame: ForecastFrame) -> dict[ForecastEntity, list[tuple[date, float]]]:
    grouped: dict[ForecastEntity, list[tuple[date, float]]] = defaultdict(list)
    for row in frame.rows:
        grouped[row.entity].append((row.period_start, row.target))
    return {entity: sorted(points) for entity, points in grouped.items()}


def observables_index(
    rows: Sequence[WeeklyObservables],
) -> dict[tuple[str, str, date], WeeklyObservables]:
    return {(row.store_code, row.category_code, row.period_start): row for row in rows}


def fit_identifier_maps(
    frame: ForecastFrame,
    *,
    stores: Sequence[StoreRow] = (),
) -> IdentifierMaps:
    """Map store and category codes to dense ids starting at 1.

    When ``stores`` is empty, region and type encodings stay empty (unknown = 0).
    """
    store_codes = sorted({row.store_code for row in frame.rows})
    category_codes = sorted({row.category_code for row in frame.rows})
    store_id = {code: index for index, code in enumerate(store_codes, start=1)}
    category_id = {code: index for index, code in enumerate(category_codes, start=1)}

    region_names = sorted({store.region for store in stores})
    type_names = sorted({store.store_type for store in stores})
    region_ids = {name: index for index, name in enumerate(region_names, start=1)}
    type_ids = {name: index for index, name in enumerate(type_names, start=1)}
    store_region = {store.code: region_ids[store.region] for store in stores}
    store_type = {store.code: type_ids[store.store_type] for store in stores}
    return IdentifierMaps(
        store_id=store_id,
        category_id=category_id,
        store_region=store_region,
        store_type=store_type,
    )


def build_observables(dataset: Dataset, weeks: Sequence[date]) -> tuple[WeeklyObservables, ...]:
    """Aggregate daily price, discount, promotion and stock to store-category weeks."""
    week_set = set(weeks)
    sku_to_category = {product.sku: product.category_code for product in dataset.catalog.products}
    stores = [store.code for store in dataset.catalog.stores]
    categories = sorted({product.category_code for product in dataset.catalog.products})

    buckets: dict[tuple[str, str, date], list[tuple[int, float, float, bool, int]]] = defaultdict(
        list
    )
    for sale in dataset.sales:
        category = sku_to_category.get(sale.product_sku)
        if category is None:
            continue
        week = iso_week_start(sale.business_date)
        if week not in week_set:
            continue
        buckets[(sale.store_code, category, week)].append(
            (
                sale.units_sold,
                float(sale.unit_price),
                float(sale.discount_amount),
                sale.promotion,
                sale.stock_on_hand,
            )
        )

    rows = [
        _aggregate_week(store, category, week, buckets.get((store, category, week), ()))
        for store in stores
        for category in categories
        for week in weeks
    ]
    return tuple(rows)


def row_feature_values(
    *,
    entity: ForecastEntity,
    period_start: date,
    cutoff: date,
    horizon_step: int,
    config: FeatureConfig,
    targets: dict[tuple[str, str, date], float],
    series: Sequence[tuple[date, float]],
    commercial: dict[tuple[str, str, date], WeeklyObservables],
    identifiers: IdentifierMaps,
) -> tuple[float, ...]:
    """Build one aligned feature vector. History after ``cutoff`` is ignored."""
    values: dict[str, float] = {"horizon_step": float(horizon_step)}
    if config.include_calendar:
        values.update(weekly_calendar_features(period_start, config.holidays))
    for lag in config.lags:
        values[f"lag_{lag}"] = lag_value(
            targets, entity, period_start=period_start, lag=lag, cutoff=cutoff
        )
    values.update(
        rolling_values(
            series,
            period_start=period_start,
            cutoff=cutoff,
            window=config.rolling_window,
            stats=config.rolling_stats,
            include_min_max=config.rolling_min_max,
        )
    )
    if config.include_commercial_lags:
        values.update(
            commercial_lag_values(commercial, entity, period_start=period_start, cutoff=cutoff)
        )
    if config.include_identifiers:
        store_id, category_id, region_id, type_id = identifiers.encode(
            entity.store_code, entity.category_code
        )
        values["store_id"] = store_id
        values["category_id"] = category_id
        values["store_region_id"] = region_id
        values["store_type_id"] = type_id
    return tuple(values[name] for name in config.feature_names())


def _rolling_stat(values: Sequence[float], stat: str) -> float:
    if not values:
        return 0.0
    if stat == "mean":
        return sum(values) / len(values)
    if stat == "median":
        return float(median(values))
    if stat == "std":
        return float(pstdev(values)) if len(values) > 1 else 0.0
    raise ValueError(f"unsupported rolling stat {stat!r}")


def _aggregate_week(
    store: str,
    category: str,
    week: date,
    rows: Sequence[tuple[int, float, float, bool, int]],
) -> WeeklyObservables:
    if not rows:
        return WeeklyObservables(store, category, week, 0.0, 0.0, 0.0, 0.0, 0.0)
    units = sum(row[0] for row in rows)
    if units > 0:
        avg_price = sum(row[0] * row[1] for row in rows) / units
        avg_discount = sum(row[0] * row[2] for row in rows) / units
    else:
        avg_price = sum(row[1] for row in rows) / len(rows)
        avg_discount = sum(row[2] for row in rows) / len(rows)
    promo_rate = sum(1.0 if row[3] else 0.0 for row in rows) / len(rows)
    avg_stock = sum(row[4] for row in rows) / len(rows)
    stockout_rate = sum(1.0 if row[4] == 0 else 0.0 for row in rows) / len(rows)
    return WeeklyObservables(
        store_code=store,
        category_code=category,
        period_start=week,
        avg_price=avg_price,
        avg_discount=avg_discount,
        promo_rate=promo_rate,
        avg_stock=avg_stock,
        stockout_rate=stockout_rate,
    )
