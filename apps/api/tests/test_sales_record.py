"""SalesRecord: the daily sales fact, its natural key and its measures."""

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from retailops_api.domain.models import SalesRecord
from tests.factories import make_product, make_store

BUSINESS_DATE = date(2026, 3, 15)


@pytest.fixture
def defaults(session: Session) -> dict[str, Any]:
    """A complete, valid sales row that each test overrides one field of."""
    return {
        "store_id": make_store(session, code="ST-001").id,
        "product_id": make_product(session, sku="SKU-1001").id,
        "business_date": BUSINESS_DATE,
        "units_sold": 12,
        "unit_price": Decimal("19.9900"),
        "stock_on_hand": 40,
    }


def _add(session: Session, defaults: dict[str, Any], **overrides: Any) -> SalesRecord:
    record = SalesRecord(**{**defaults, **overrides})
    session.add(record)
    session.flush()
    return record


def test_a_sales_row_captures_the_trading_day(session: Session, defaults: dict[str, Any]) -> None:
    record = _add(session, defaults)
    session.refresh(record)

    assert record.id is not None
    assert record.business_date == BUSINESS_DATE
    assert record.units_sold == 12
    assert record.unit_price == Decimal("19.9900")
    assert record.stock_on_hand == 40


def test_discount_and_promotion_default_to_no_promotion(
    session: Session, defaults: dict[str, Any]
) -> None:
    record = _add(session, defaults)
    session.expire_all()
    session.refresh(record)

    assert record.discount_amount == Decimal("0")
    assert record.promotion is False


def test_business_date_is_a_calendar_day(session: Session, defaults: dict[str, Any]) -> None:
    """ADR-002: a trading day, not an instant, so no timezone can shift it."""
    record = _add(session, defaults)
    session.expire_all()
    session.refresh(record)

    assert isinstance(record.business_date, date)
    assert record.business_date.isoformat() == "2026-03-15"


def test_the_natural_key_is_unique(session: Session, defaults: dict[str, Any]) -> None:
    """One row per store, product and trading day."""
    _add(session, defaults)

    with pytest.raises(IntegrityError):
        _add(session, defaults, units_sold=99)


def test_the_same_product_sells_in_several_stores_on_one_day(
    session: Session, defaults: dict[str, Any]
) -> None:
    _add(session, defaults)
    other_store = make_store(session, code="ST-002")

    _add(session, defaults, store_id=other_store.id)

    assert session.query(SalesRecord).count() == 2


def test_a_store_sells_the_same_product_on_consecutive_days(
    session: Session, defaults: dict[str, Any]
) -> None:
    _add(session, defaults, business_date=date(2026, 3, 15))
    _add(session, defaults, business_date=date(2026, 3, 16))

    assert session.query(SalesRecord).count() == 2


def test_a_day_with_no_sales_is_a_valid_row(session: Session, defaults: dict[str, Any]) -> None:
    """Zero-sales days matter to forecasting; they are not missing data."""
    record = _add(session, defaults, units_sold=0, stock_on_hand=0)

    assert record.units_sold == 0
    assert record.stock_on_hand == 0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("units_sold", -1),
        ("unit_price", Decimal("-0.0001")),
        ("discount_amount", Decimal("-0.0001")),
        ("stock_on_hand", -1),
    ],
)
def test_negative_measures_are_rejected(
    session: Session, defaults: dict[str, Any], field: str, value: object
) -> None:
    with pytest.raises(IntegrityError):
        _add(session, defaults, **{field: value})


def test_store_must_exist(session: Session, defaults: dict[str, Any]) -> None:
    with pytest.raises(IntegrityError):
        _add(session, defaults, store_id=999_999)


def test_product_must_exist(session: Session, defaults: dict[str, Any]) -> None:
    with pytest.raises(IntegrityError):
        _add(session, defaults, product_id=999_999)


def test_a_store_with_sales_history_cannot_be_deleted(
    session: Session, defaults: dict[str, Any]
) -> None:
    record = _add(session, defaults)

    session.delete(session.get_one(type(record.store), defaults["store_id"]))
    with pytest.raises(IntegrityError):
        session.flush()


def test_a_product_with_sales_history_cannot_be_deleted(
    session: Session, defaults: dict[str, Any]
) -> None:
    record = _add(session, defaults)

    session.delete(session.get_one(type(record.product), defaults["product_id"]))
    with pytest.raises(IntegrityError):
        session.flush()


def test_money_survives_the_round_trip_exactly(session: Session, defaults: dict[str, Any]) -> None:
    record = _add(
        session, defaults, unit_price=Decimal("1234.5678"), discount_amount=Decimal("0.0001")
    )
    session.expire_all()
    session.refresh(record)

    assert isinstance(record.unit_price, Decimal)
    assert record.unit_price == Decimal("1234.5678")
    assert record.discount_amount == Decimal("0.0001")
