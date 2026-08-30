"""Purchase orders: identity, money, quantities and constraints."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from retailops_api.domain.models import PurchaseOrder, PurchaseOrderLine
from retailops_api.domain.models.purchase_order import PurchaseOrderStatus
from tests.factories import (
    make_product,
    make_purchase_order,
    make_purchase_order_line,
    make_store,
    make_supplier,
)


def test_an_order_records_supplier_store_dates_and_currency(session: Session) -> None:
    supplier = make_supplier(session)
    store = make_store(session)
    order = make_purchase_order(
        session,
        supplier,
        store,
        po_number="PO-8801",
        order_date=date(2026, 3, 1),
        expected_date=date(2026, 3, 10),
        currency="MXN",
    )
    session.refresh(order)

    assert order.id is not None
    assert order.supplier_id == supplier.id
    assert order.store_id == store.id
    assert order.status == PurchaseOrderStatus.open.value
    assert order.currency == "MXN"
    assert order.active is True
    assert order.created_at is not None
    assert order.updated_at is not None


def test_a_line_stores_quantity_cost_tax_and_total(session: Session) -> None:
    supplier = make_supplier(session)
    store = make_store(session)
    product = make_product(session)
    order = make_purchase_order(session, supplier, store)
    line = make_purchase_order_line(
        session,
        order,
        product,
        ordered_quantity=24,
        unit_cost=Decimal("7.4500"),
        tax_rate=Decimal("16.0000"),
    )
    session.expire_all()
    session.refresh(line)

    assert line.ordered_quantity == 24
    assert line.unit_cost == Decimal("7.4500")
    assert line.tax_amount == Decimal("28.6080")
    assert line.line_total == Decimal("207.4080")


def test_po_number_is_unique_per_supplier(session: Session) -> None:
    supplier = make_supplier(session)
    store = make_store(session)
    make_purchase_order(session, supplier, store, po_number="PO-1")

    with pytest.raises(IntegrityError):
        make_purchase_order(session, supplier, store, po_number="PO-1")


def test_two_suppliers_may_reuse_a_po_number(session: Session) -> None:
    store = make_store(session)
    first = make_supplier(session, code="SUP-1")
    second = make_supplier(session, code="SUP-2")
    make_purchase_order(session, first, store, po_number="PO-1")
    make_purchase_order(session, second, store, po_number="PO-1")

    assert session.query(PurchaseOrder).count() == 2


def test_line_number_is_unique_within_an_order(session: Session) -> None:
    supplier = make_supplier(session)
    store = make_store(session)
    product = make_product(session, sku="SKU-1")
    other = make_product(session, sku="SKU-2")
    order = make_purchase_order(session, supplier, store)
    make_purchase_order_line(session, order, product, line_number=1)

    with pytest.raises(IntegrityError):
        make_purchase_order_line(session, order, other, line_number=1)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("ordered_quantity", 0),
        ("ordered_quantity", -1),
        ("unit_cost", Decimal("-0.0001")),
        ("tax_rate", Decimal("-1")),
        ("line_number", 0),
    ],
)
def test_impossible_line_values_are_rejected(session: Session, field: str, value: object) -> None:
    supplier = make_supplier(session)
    store = make_store(session)
    product = make_product(session)
    order = make_purchase_order(session, supplier, store)
    kwargs: dict[str, object] = {
        "ordered_quantity": 10,
        "unit_cost": Decimal("1.0000"),
        "tax_rate": Decimal("0"),
        "line_number": 1,
    }
    kwargs[field] = value
    with pytest.raises(IntegrityError):
        make_purchase_order_line(session, order, product, **kwargs)  # type: ignore[arg-type]


def test_unknown_status_is_rejected(session: Session) -> None:
    supplier = make_supplier(session)
    store = make_store(session)

    with pytest.raises(IntegrityError):
        make_purchase_order(session, supplier, store, status="invented")


def test_deleting_an_order_removes_its_lines(session: Session) -> None:
    supplier = make_supplier(session)
    store = make_store(session)
    product = make_product(session)
    order = make_purchase_order(session, supplier, store)
    make_purchase_order_line(session, order, product)

    session.delete(order)
    session.flush()

    assert session.query(PurchaseOrder).count() == 0
    assert session.query(PurchaseOrderLine).count() == 0


def test_a_product_on_an_order_cannot_be_deleted(session: Session) -> None:
    supplier = make_supplier(session)
    store = make_store(session)
    product = make_product(session)
    order = make_purchase_order(session, supplier, store)
    make_purchase_order_line(session, order, product)

    session.delete(product)
    with pytest.raises(IntegrityError):
        session.flush()
