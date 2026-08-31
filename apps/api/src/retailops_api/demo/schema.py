"""Apply Alembic revisions to the configured database."""

from __future__ import annotations

from alembic import command
from alembic.config import Config

from retailops_api.demo.paths import api_root


def upgrade_schema() -> None:
    """Bring the configured database to the current Alembic head."""

    root = api_root()
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    command.upgrade(config, "head")
