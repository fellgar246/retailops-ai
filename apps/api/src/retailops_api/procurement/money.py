"""Decimal-safe line arithmetic. Floats never enter these calculations."""

from __future__ import annotations

from decimal import Decimal

from retailops_api.dataset.contract import MONEY_QUANT, quantize_money

HUNDRED = Decimal("100")


def extended_amount(quantity: int, unit_cost: Decimal) -> Decimal:
    return quantize_money(Decimal(quantity) * unit_cost)


def tax_on(extended: Decimal, tax_rate: Decimal) -> Decimal:
    return quantize_money(extended * tax_rate / HUNDRED)


def line_amounts(
    quantity: int, unit_cost: Decimal, tax_rate: Decimal
) -> tuple[Decimal, Decimal, Decimal]:
    """Return ``(extended, tax_amount, line_total)`` at stored money scale."""
    extended = extended_amount(quantity, unit_cost)
    tax_amount = tax_on(extended, tax_rate)
    return extended, tax_amount, quantize_money(extended + tax_amount)


def format_money(value: Decimal) -> str:
    return str(quantize_money(value))


def format_quantity(value: int) -> str:
    return str(value)


def format_rate(value: Decimal) -> str:
    return format(value.quantize(MONEY_QUANT), "f")


def quantity_within(expected: int, actual: int, tolerance: int) -> bool:
    return abs(actual - expected) <= tolerance


def money_within(
    expected: Decimal,
    actual: Decimal,
    *,
    monetary_tolerance: Decimal,
    percent_tolerance: Decimal,
) -> bool:
    """Pass when the absolute difference or the percent-of-expected is inside tolerance."""
    diff = abs(actual - expected)
    if diff <= monetary_tolerance:
        return True
    if expected == 0:
        return False
    percent = (diff / abs(expected)) * HUNDRED
    return percent <= percent_tolerance
