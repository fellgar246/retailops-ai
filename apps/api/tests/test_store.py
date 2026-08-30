"""Store: code uniqueness and the attributes stores are grouped by."""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from retailops_api.domain.models import Store
from tests.factories import make_store


def test_store_records_its_grouping_attributes(session: Session) -> None:
    store = make_store(
        session, code="ST-001", name="Centro Flagship", region="Central", store_type="flagship"
    )

    assert store.id is not None
    assert store.region == "Central"
    assert store.store_type == "flagship"
    assert store.active is True


def test_duplicate_code_is_rejected(session: Session) -> None:
    make_store(session, code="ST-001")

    with pytest.raises(IntegrityError):
        make_store(session, code="ST-001", name="Duplicate")


def test_region_is_required(session: Session) -> None:
    session.add(Store(code="ST-001", name="No Region", region=None, store_type="express"))

    with pytest.raises(IntegrityError):
        session.flush()


def test_store_type_is_required(session: Session) -> None:
    session.add(Store(code="ST-001", name="No Type", region="Central", store_type=None))

    with pytest.raises(IntegrityError):
        session.flush()


def test_stores_can_be_filtered_by_region(session: Session) -> None:
    make_store(session, code="ST-001", region="Central")
    make_store(session, code="ST-002", region="North")
    make_store(session, code="ST-003", region="North")

    northern = session.scalars(select(Store.code).where(Store.region == "North")).all()

    assert set(northern) == {"ST-002", "ST-003"}
