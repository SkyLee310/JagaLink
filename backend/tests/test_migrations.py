from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import Engine, inspect

from app.db import models  # noqa: F401  (registers the tables on Base.metadata)
from app.db.base import Base

TABLES = {
    "community",
    "zone",
    "node",
    "link",
    "app_user",
    "scenario",
    "scenario_run",
    "event",
    "track",
    "track_segment",
}


def tables(engine: Engine) -> set[str]:
    return set(inspect(engine).get_table_names())


def test_upgrade_and_downgrade_round_trip(engine: Engine, alembic_cfg: Config) -> None:
    try:
        command.downgrade(alembic_cfg, "base")
        assert not TABLES & tables(engine)
        command.upgrade(alembic_cfg, "head")
        assert tables(engine) >= TABLES
    finally:
        command.upgrade(alembic_cfg, "head")


def test_models_match_the_migrations(engine: Engine) -> None:
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    assert diff == []
