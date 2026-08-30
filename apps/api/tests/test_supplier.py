"""Supplier: code uniqueness and tax ID treatment."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tests.factories import make_supplier


def test_supplier_requires_only_code_and_name(session: Session) -> None:
    supplier = make_supplier(session, code="SUP-BEVCO", name="BevCo Distribution")

    assert supplier.id is not None
    assert supplier.tax_id is None
    assert supplier.active is True


def test_duplicate_code_is_rejected(session: Session) -> None:
    make_supplier(session, code="SUP-BEVCO")

    with pytest.raises(IntegrityError):
        make_supplier(session, code="SUP-BEVCO", name="Impostor")


def test_tax_id_is_stored_verbatim(session: Session) -> None:
    """ADR-002: no normalisation, no country-specific validation."""
    supplier = make_supplier(session, code="SUP-1", tax_id="  bev920304-ab1 ")
    session.refresh(supplier)

    assert supplier.tax_id == "  bev920304-ab1 "


def test_two_suppliers_may_share_a_tax_id(session: Session) -> None:
    """One legal entity can trade as several suppliers, so tax_id is not unique."""
    make_supplier(session, code="SUP-1", tax_id="BEV920304AB1")
    make_supplier(session, code="SUP-2", tax_id="BEV920304AB1")


def test_a_supplier_can_be_deactivated(session: Session) -> None:
    supplier = make_supplier(session, code="SUP-1")

    supplier.active = False
    session.flush()
    session.refresh(supplier)

    assert supplier.active is False
