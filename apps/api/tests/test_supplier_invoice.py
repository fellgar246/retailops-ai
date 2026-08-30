"""Supplier invoices: identity, money and duplicate prevention."""

from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from retailops_api.domain.models import SupplierInvoice, SupplierInvoiceLine
from tests.factories import (
    make_product,
    make_purchase_order,
    make_store,
    make_supplier,
    make_supplier_invoice,
    make_supplier_invoice_line,
)


def test_an_invoice_records_supplier_number_date_and_optional_po(session: Session) -> None:
    supplier = make_supplier(session)
    store = make_store(session)
    order = make_purchase_order(session, supplier, store, po_number="PO-1001")
    invoice = make_supplier_invoice(
        session, supplier, invoice_number="INV-4401", purchase_order=order, currency="MXN"
    )

    assert invoice.purchase_order_id == order.id
    assert invoice.po_number == "PO-1001"
    assert invoice.currency == "MXN"


def test_an_invoice_line_can_be_stored_without_a_product(session: Session) -> None:
    supplier = make_supplier(session)
    invoice = make_supplier_invoice(session, supplier)
    line = make_supplier_invoice_line(
        session,
        invoice,
        product=None,
        supplier_sku="UNKNOWN",
        ean=None,
        invoiced_quantity=5,
        unit_cost=Decimal("1.0000"),
        tax_rate=Decimal("0"),
    )

    assert line.product_id is None
    assert line.supplier_sku == "UNKNOWN"


def test_invoice_number_is_unique_per_supplier(session: Session) -> None:
    supplier = make_supplier(session)
    make_supplier_invoice(session, supplier, invoice_number="INV-1")

    with pytest.raises(IntegrityError):
        make_supplier_invoice(session, supplier, invoice_number="INV-1")


def test_two_suppliers_may_reuse_an_invoice_number(session: Session) -> None:
    first = make_supplier(session, code="SUP-1")
    second = make_supplier(session, code="SUP-2")
    make_supplier_invoice(session, first, invoice_number="INV-1")
    make_supplier_invoice(session, second, invoice_number="INV-1")

    assert session.query(SupplierInvoice).count() == 2


def test_invoiced_quantity_must_be_positive(session: Session) -> None:
    supplier = make_supplier(session)
    product = make_product(session)
    invoice = make_supplier_invoice(session, supplier)

    with pytest.raises(IntegrityError):
        make_supplier_invoice_line(session, invoice, product=product, invoiced_quantity=0)


def test_unknown_status_is_rejected(session: Session) -> None:
    supplier = make_supplier(session)

    with pytest.raises(IntegrityError):
        make_supplier_invoice(session, supplier, status="invented")


def test_deleting_an_invoice_removes_its_lines(session: Session) -> None:
    supplier = make_supplier(session)
    product = make_product(session)
    invoice = make_supplier_invoice(session, supplier)
    make_supplier_invoice_line(session, invoice, product=product)

    session.delete(invoice)
    session.flush()

    assert session.query(SupplierInvoice).count() == 0
    assert session.query(SupplierInvoiceLine).count() == 0
