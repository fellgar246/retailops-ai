"""Category: the merchandise hierarchy and its uniqueness rules."""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from retailops_api.domain.models import Category
from tests.factories import make_category, make_product


def test_root_category_has_no_parent(session: Session) -> None:
    root = make_category(session, code="BEV", name="Beverages")

    assert root.id is not None
    assert root.parent_id is None
    assert root.parent is None
    assert root.active is True


def test_child_category_links_to_its_parent(session: Session) -> None:
    root = make_category(session, code="BEV", name="Beverages")
    child = make_category(session, code="BEV-SOFT", name="Soft Drinks", parent=root)

    assert child.parent_id == root.id
    assert child.parent is root
    assert child.children == []


def test_parent_exposes_its_children(session: Session) -> None:
    root = make_category(session, code="BEV")
    first = make_category(session, code="BEV-SOFT", parent=root)
    second = make_category(session, code="BEV-WATER", parent=root)

    session.refresh(root)

    assert {child.code for child in root.children} == {first.code, second.code}


def test_hierarchy_can_nest_more_than_one_level(session: Session) -> None:
    root = make_category(session, code="HOME")
    mid = make_category(session, code="HOME-CLEAN", parent=root)
    leaf = make_category(session, code="HOME-CLEAN-SPRAY", parent=mid)

    assert leaf.parent is not None
    assert leaf.parent.parent is root


def test_duplicate_code_is_rejected(session: Session) -> None:
    make_category(session, code="BEV", name="Beverages")

    with pytest.raises(IntegrityError):
        make_category(session, code="BEV", name="Different Name")


def test_a_category_cannot_be_its_own_parent(session: Session) -> None:
    category = make_category(session, code="BEV")

    category.parent_id = category.id
    with pytest.raises(IntegrityError):
        session.flush()


def test_parent_must_reference_an_existing_category(session: Session) -> None:
    category = make_category(session, code="BEV")

    category.parent_id = category.id + 10_000
    with pytest.raises(IntegrityError):
        session.flush()


def test_a_referenced_parent_cannot_be_deleted(session: Session) -> None:
    root = make_category(session, code="BEV")
    make_category(session, code="BEV-SOFT", parent=root)

    session.delete(root)
    with pytest.raises(IntegrityError):
        session.flush()


def test_a_category_in_use_by_a_product_cannot_be_deleted(session: Session) -> None:
    category = make_category(session, code="BEV")
    make_product(session, sku="SKU-1", category=category)

    session.delete(category)
    with pytest.raises(IntegrityError):
        session.flush()


def test_a_category_can_be_deactivated_instead_of_deleted(session: Session) -> None:
    category = make_category(session, code="BEV")
    make_product(session, sku="SKU-1", category=category)

    category.active = False
    session.flush()

    stored = session.scalar(select(Category).where(Category.code == "BEV"))
    assert stored is not None
    assert stored.active is False


def test_timestamps_are_set_by_the_database(session: Session) -> None:
    category = make_category(session, code="BEV")
    session.refresh(category)

    assert category.created_at is not None
    assert category.updated_at is not None
