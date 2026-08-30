"""Daily demand, prices, promotions and stock — including lost-demand behaviour.

Unconstrained demand is never a function of a single factor. It combines
product popularity, category and store effects, a yearly seasonal curve,
the calendar multiplier, promotional lift and multiplicative noise. Stock
then censors what is actually sold, so a zero-sales day is not automatically
a zero-demand day.
"""

from __future__ import annotations

import math
from collections.abc import Iterator, Sequence
from datetime import date, timedelta
from decimal import Decimal
from random import Random

from retailops_api.dataset.contract import CalendarDay, SalesRow, quantize_money
from retailops_api.synthetic.calendar import calendar_by_date, iter_dates
from retailops_api.synthetic.catalog import CatalogArtifacts
from retailops_api.synthetic.config import GeneratorConfig

_BASE_UNITS = 10.0
_SEASONAL_AMPLITUDE = 0.15
# Peak around late October so Q4 is busy without collapsing into Christmas.
_SEASONAL_PEAK_DAY = 300
_Q4_LIFT = 1.08
_PROMO_MEAN_DAYS = 5
_PROMO_LIFT_RANGE = (1.25, 1.60)
_STOCKOUT_MEAN_DAYS = 2
_PRICE_JITTER = 0.02
_NOISE_SIGMA = 0.18


def generate_sales(
    config: GeneratorConfig,
    artifacts: CatalogArtifacts,
    calendar: Sequence[CalendarDay],
) -> tuple[SalesRow, ...]:
    return tuple(iter_sales(config, artifacts, calendar))


def iter_sales(
    config: GeneratorConfig,
    artifacts: CatalogArtifacts,
    calendar: Sequence[CalendarDay],
) -> Iterator[SalesRow]:
    """Yield one sales row per store, product and trading day, in a stable order."""
    rng = Random(config.demand_seed)
    catalog = artifacts.catalog
    stores = sorted(catalog.stores, key=lambda store: store.code)
    products = sorted(catalog.products, key=lambda product: product.sku)
    days = calendar_by_date(calendar)
    restock_weekday = {store.code: rng.randint(0, 5) for store in stores}

    stock: dict[tuple[str, str], int] = {}
    reorder_point: dict[tuple[str, str], int] = {}
    for store in stores:
        for product in products:
            typical = (
                _BASE_UNITS
                * artifacts.popularity[product.sku]
                * artifacts.category_effect.get(product.category_code, 1.0)
                * artifacts.store_effect[store.code]
            )
            opening = max(4, round(typical * rng.uniform(8.0, 16.0)))
            stock[(store.code, product.sku)] = opening
            reorder_point[(store.code, product.sku)] = max(2, round(typical * 4))

    promo_until: dict[str, date] = {}
    stockout_until: dict[tuple[str, str], date] = {}
    promo_start_p = _daily_start_probability(config.promotion_probability, _PROMO_MEAN_DAYS)
    stockout_start_p = _daily_start_probability(config.stockout_probability, _STOCKOUT_MEAN_DAYS)

    for day in iter_dates(config.start_date, config.end_date):
        features = days[day]
        for product in products:
            until = promo_until.get(product.sku)
            if until is None or until < day:
                if rng.random() < promo_start_p:
                    length = rng.randint(3, 7)
                    promo_until[product.sku] = day + timedelta(days=length - 1)
                else:
                    promo_until.pop(product.sku, None)

        for store in stores:
            for product in products:
                key = (store.code, product.sku)
                on_promo = promo_until.get(product.sku, date.min) >= day

                out_until = stockout_until.get(key)
                if out_until is not None and out_until >= day:
                    stock[key] = 0
                elif rng.random() < stockout_start_p:
                    length = rng.randint(1, 3)
                    stockout_until[key] = day + timedelta(days=length - 1)
                    stock[key] = 0

                unconstrained = _unconstrained_demand(
                    rng,
                    day,
                    features.demand_multiplier,
                    popularity=artifacts.popularity[product.sku],
                    category_effect=artifacts.category_effect.get(product.category_code, 1.0),
                    store_effect=artifacts.store_effect[store.code],
                    promo_lift=rng.uniform(*_PROMO_LIFT_RANGE) if on_promo else 1.0,
                )
                opening = max(0, stock[key])
                sold = min(round(unconstrained), opening)
                closing = opening - sold

                pack = artifacts.case_pack[product.sku]
                if (
                    closing <= reorder_point[key]
                    and day.weekday() == restock_weekday[store.code]
                    and (out_until is None or out_until < day)
                ):
                    cases = max(1, math.ceil((reorder_point[key] * 3 - closing) / pack))
                    closing += pack * cases

                stock[key] = closing
                unit_price, discount = _price(
                    rng, artifacts.list_price[product.sku], on_promo=on_promo
                )
                yield SalesRow(
                    store_code=store.code,
                    product_sku=product.sku,
                    business_date=day,
                    units_sold=sold,
                    unit_price=unit_price,
                    discount_amount=discount,
                    promotion=on_promo,
                    stock_on_hand=closing,
                )


def _unconstrained_demand(
    rng: Random,
    day: date,
    calendar_multiplier: float,
    *,
    popularity: float,
    category_effect: float,
    store_effect: float,
    promo_lift: float,
) -> float:
    seasonal = 1.0 + _SEASONAL_AMPLITUDE * math.sin(
        2.0 * math.pi * (day.timetuple().tm_yday - _SEASONAL_PEAK_DAY) / 365.25
    )
    if day.month >= 11:
        seasonal *= _Q4_LIFT
    noise = rng.lognormvariate(0.0, _NOISE_SIGMA)
    return max(
        0.0,
        _BASE_UNITS
        * popularity
        * category_effect
        * store_effect
        * seasonal
        * calendar_multiplier
        * promo_lift
        * noise,
    )


def _price(rng: Random, list_price: Decimal, *, on_promo: bool) -> tuple[Decimal, Decimal]:
    if on_promo:
        fraction = Decimal(str(round(rng.uniform(0.10, 0.25), 4)))
        discount = quantize_money(list_price * fraction)
        charged = quantize_money(list_price - discount)
        if charged < Decimal("0"):
            charged = Decimal("0.0000")
            discount = list_price
        return charged, discount
    jitter = Decimal(str(round(rng.uniform(-_PRICE_JITTER, _PRICE_JITTER), 4)))
    charged = quantize_money(list_price * (Decimal("1") + jitter))
    return max(charged, Decimal("0.0000")), Decimal("0.0000")


def _daily_start_probability(target_fraction: float, mean_duration_days: int) -> float:
    """Approximate per-day start rate so the duty cycle matches ``target_fraction``."""
    if target_fraction <= 0:
        return 0.0
    if target_fraction >= 1:
        return 1.0
    return min(1.0, target_fraction / mean_duration_days)
