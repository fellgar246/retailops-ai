"""Product: SKU and barcode uniqueness, and the required category."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from retailops_api.domain.models import Product
from tests.factories import make_category, make_product


def test_product_requires_only_sku_name_and_category(session: Session) -> None:
    category = make_category(session, code="BEV-SOFT")
    product = make_product(session, sku="SKU-1001", name="Cola 355ml", category=category)

    assert product.id is not None
    assert product.category is category
    assert product.description is None
    assert product.ean is None
    assert product.active is True


def test_duplicate_sku_is_rejected(session: Session) -> None:
    make_product(session, sku="SKU-1001")

    with pytest.raises(IntegrityError):
        make_product(session, sku="SKU-1001", name="Another Product")


def test_duplicate_ean_is_rejected(session: Session) -> None:
    make_product(session, sku="SKU-1001", ean="7501000110018")

    with pytest.raises(IntegrityError):
        make_product(session, sku="SKU-1002", ean="7501000110018")


def test_many_products_may_have_no_ean(session: Session) -> None:
    """Nullable-unique: absent barcodes must not collide with each other."""
    make_product(session, sku="SKU-1001", ean=None)
    make_product(session, sku="SKU-1002", ean=None)
    make_product(session, sku="SKU-1003", ean=None)

    assert session.query(Product).filter(Product.ean.is_(None)).count() == 3


def test_category_is_required(session: Session) -> None:
    product = Product(sku="SKU-1001", name="Orphan", category_id=None)
    session.add(product)

    with pytest.raises(IntegrityError):
        session.flush()


def test_category_must_exist(session: Session) -> None:
    product = Product(sku="SKU-1001", name="Dangling", category_id=999_999)
    session.add(product)

    with pytest.raises(IntegrityError):
        session.flush()


def test_products_from_different_categories_coexist(session: Session) -> None:
    soft = make_category(session, code="BEV-SOFT")
    chips = make_category(session, code="SNACK-CHIPS")

    cola = make_product(session, sku="SKU-1001", category=soft)
    crisps = make_product(session, sku="SKU-2001", category=chips)

    assert cola.category_id != crisps.category_id


def test_description_accepts_long_text(session: Session) -> None:
    long_text = "A very detailed product description. " * 100
    product = make_product(session, sku="SKU-1001", description=long_text)
    session.refresh(product)

    assert product.description == long_text
