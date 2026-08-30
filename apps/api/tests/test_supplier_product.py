"""SupplierProduct: the commercial terms of one supplier/product pairing."""

from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from retailops_api.domain.models import SupplierProduct
from tests.factories import make_product, make_supplier, make_supplier_product


def test_terms_are_stored_on_the_relationship(session: Session) -> None:
    supplier = make_supplier(session, code="SUP-BEVCO")
    product = make_product(session, sku="SKU-1001")

    link = make_supplier_product(
        session,
        supplier,
        product,
        cost=Decimal("7.4500"),
        case_pack=24,
        minimum_order_quantity=2,
        lead_time_days=3,
        supplier_sku="BC-COLA-355",
    )
    session.refresh(link)

    assert link.cost == Decimal("7.4500")
    assert link.case_pack == 24
    assert link.minimum_order_quantity == 2
    assert link.lead_time_days == 3
    assert link.supplier_sku == "BC-COLA-355"
    assert link.active is True


def test_the_same_pairing_cannot_be_registered_twice(session: Session) -> None:
    supplier = make_supplier(session, code="SUP-1")
    product = make_product(session, sku="SKU-1001")
    make_supplier_product(session, supplier, product)

    with pytest.raises(IntegrityError):
        make_supplier_product(session, supplier, product, cost=Decimal("9.9900"))


def test_one_product_may_have_several_suppliers(session: Session) -> None:
    """This is what makes supplier comparison possible at all."""
    product = make_product(session, sku="SKU-1001")
    first = make_supplier(session, code="SUP-1")
    second = make_supplier(session, code="SUP-2")

    make_supplier_product(session, first, product, cost=Decimal("7.4500"), lead_time_days=3)
    make_supplier_product(session, second, product, cost=Decimal("7.9900"), lead_time_days=10)

    assert session.query(SupplierProduct).filter_by(product_id=product.id).count() == 2


def test_one_supplier_may_offer_several_products(session: Session) -> None:
    supplier = make_supplier(session, code="SUP-1")
    first = make_product(session, sku="SKU-1001")
    second = make_product(session, sku="SKU-1002")

    make_supplier_product(session, supplier, first)
    make_supplier_product(session, supplier, second)

    assert session.query(SupplierProduct).filter_by(supplier_id=supplier.id).count() == 2


def test_cost_of_zero_is_allowed(session: Session) -> None:
    """A free promotional line is legitimate; a negative cost is not."""
    supplier = make_supplier(session, code="SUP-1")
    product = make_product(session, sku="SKU-1001")

    link = make_supplier_product(session, supplier, product, cost=Decimal("0"))

    assert link.cost == Decimal("0")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("cost", Decimal("-0.0001")),
        ("case_pack", 0),
        ("case_pack", -1),
        ("minimum_order_quantity", -1),
        ("lead_time_days", -1),
    ],
)
def test_impossible_terms_are_rejected(session: Session, field: str, value: object) -> None:
    supplier = make_supplier(session, code="SUP-1")
    product = make_product(session, sku="SKU-1001")

    link = SupplierProduct(
        supplier_id=supplier.id,
        product_id=product.id,
        cost=Decimal("1.0000"),
        case_pack=12,
        minimum_order_quantity=1,
        lead_time_days=1,
    )
    setattr(link, field, value)
    session.add(link)

    with pytest.raises(IntegrityError):
        session.flush()


def test_cost_keeps_four_decimal_places(session: Session) -> None:
    """Per-unit cost inside a case is rarely a round number. See ADR-002."""
    supplier = make_supplier(session, code="SUP-1")
    product = make_product(session, sku="SKU-1001")

    link = make_supplier_product(session, supplier, product, cost=Decimal("0.8329"))
    session.expire_all()
    session.refresh(link)

    assert isinstance(link.cost, Decimal)
    assert link.cost == Decimal("0.8329")


def test_supplier_must_exist(session: Session) -> None:
    product = make_product(session, sku="SKU-1001")
    session.add(SupplierProduct(supplier_id=999_999, product_id=product.id, cost=Decimal("1.0000")))

    with pytest.raises(IntegrityError):
        session.flush()


def test_a_supplier_with_terms_cannot_be_deleted(session: Session) -> None:
    supplier = make_supplier(session, code="SUP-1")
    product = make_product(session, sku="SKU-1001")
    make_supplier_product(session, supplier, product)

    session.delete(supplier)
    with pytest.raises(IntegrityError):
        session.flush()
