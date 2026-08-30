"""Goods receipts: partial deliveries, PO reference and constraints."""

from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from retailops_api.domain.models import GoodsReceipt, GoodsReceiptLine
from tests.factories import (
    make_goods_receipt,
    make_goods_receipt_line,
    make_product,
    make_purchase_order,
    make_purchase_order_line,
    make_store,
    make_supplier,
)


def test_a_receipt_can_reference_a_purchase_order(session: Session) -> None:
    supplier = make_supplier(session)
    store = make_store(session)
    order = make_purchase_order(session, supplier, store, po_number="PO-1001")
    receipt = make_goods_receipt(
        session,
        supplier,
        receipt_number="GR-9",
        purchase_order=order,
        received_date=date(2026, 3, 5),
    )

    assert receipt.purchase_order_id == order.id
    assert receipt.po_number == "PO-1001"
    assert receipt.received_date == date(2026, 3, 5)


def test_a_receipt_without_a_purchase_order_is_allowed(session: Session) -> None:
    supplier = make_supplier(session)
    receipt = make_goods_receipt(session, supplier, po_number=None)

    assert receipt.purchase_order_id is None
    assert receipt.po_number is None


def test_two_receipts_can_cover_one_order(session: Session) -> None:
    """Partial delivery is several receipts against the same order."""
    supplier = make_supplier(session)
    store = make_store(session)
    product = make_product(session)
    order = make_purchase_order(session, supplier, store)
    po_line = make_purchase_order_line(session, order, product, ordered_quantity=100)
    first = make_goods_receipt(session, supplier, receipt_number="GR-1", purchase_order=order)
    second = make_goods_receipt(session, supplier, receipt_number="GR-2", purchase_order=order)
    make_goods_receipt_line(
        session, first, product, received_quantity=40, purchase_order_line=po_line
    )
    make_goods_receipt_line(
        session, second, product, received_quantity=60, purchase_order_line=po_line
    )

    received = sum(line.received_quantity for line in first.lines) + sum(
        line.received_quantity for line in second.lines
    )
    assert received == 100
    assert session.query(GoodsReceipt).count() == 2


def test_receipt_number_is_unique_per_supplier(session: Session) -> None:
    supplier = make_supplier(session)
    make_goods_receipt(session, supplier, receipt_number="GR-1")

    with pytest.raises(IntegrityError):
        make_goods_receipt(session, supplier, receipt_number="GR-1")


def test_received_quantity_must_be_positive(session: Session) -> None:
    supplier = make_supplier(session)
    product = make_product(session)
    receipt = make_goods_receipt(session, supplier)

    with pytest.raises(IntegrityError):
        make_goods_receipt_line(session, receipt, product, received_quantity=0)


def test_deleting_a_receipt_removes_its_lines(session: Session) -> None:
    supplier = make_supplier(session)
    product = make_product(session)
    receipt = make_goods_receipt(session, supplier)
    make_goods_receipt_line(session, receipt, product)

    session.delete(receipt)
    session.flush()

    assert session.query(GoodsReceipt).count() == 0
    assert session.query(GoodsReceiptLine).count() == 0


def test_an_order_with_receipts_cannot_be_deleted(session: Session) -> None:
    supplier = make_supplier(session)
    store = make_store(session)
    order = make_purchase_order(session, supplier, store)
    make_goods_receipt(session, supplier, purchase_order=order)

    session.delete(order)
    with pytest.raises(IntegrityError):
        session.flush()
