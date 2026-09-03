import os

import pytest

LIVE_AWS = os.environ.get("RETAILOPS_LIVE_AWS") == "1"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    if LIVE_AWS:
        return
    skip = pytest.mark.skip(reason="set RETAILOPS_LIVE_AWS=1 to run live AWS checks")
    for item in items:
        if item.get_closest_marker("live_aws"):
            item.add_marker(skip)
