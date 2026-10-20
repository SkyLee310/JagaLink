"""Shared fixtures: a migrated test database, and one rolled-back transaction per test."""

import os
from collections.abc import Callable, Iterator
from contextlib import nullcontext
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, make_url, text
from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.db.seed import SeedReport, seed, seed_id
from app.db.session import get_db
from app.main import create_app
from app.sim.runs import RunManager
from tests.fakes import FrozenTimer

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _test_database_url() -> str:
    """TEST_DATABASE_URL, or DATABASE_URL pointed at a separate jagalink_test database."""
    explicit = os.environ.get("TEST_DATABASE_URL")
    if explicit:
        return explicit
    url = make_url(get_settings().database_url).set(database="jagalink_test")
    return url.render_as_string(hide_password=False)


def _ensure_database(url: str) -> None:
    target = make_url(url)
    admin = create_engine(target.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            found = conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": target.database}
            )
            if not found:
                conn.execute(text(f'CREATE DATABASE "{target.database}"'))
    finally:
        admin.dispose()


@pytest.fixture(scope="session")
def alembic_cfg() -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.attributes["database_url"] = _test_database_url()
    return config


@pytest.fixture(scope="session")
def engine(alembic_cfg: Config) -> Iterator[Engine]:
    url = alembic_cfg.attributes["database_url"]
    _ensure_database(url)
    command.upgrade(alembic_cfg, "head")
    engine = create_engine(url)
    yield engine
    engine.dispose()


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    """A session whose commits land in savepoints; everything is rolled back after the test."""
    with engine.connect() as connection:
        transaction = connection.begin()
        session = Session(bind=connection, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            session.close()
            transaction.rollback()


@pytest.fixture
def seeded(db: Session) -> SeedReport:
    return seed(db)


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    # Players share the test's session and stand still until a test swaps the timer.
    app.state.runs = RunManager(timer=FrozenTimer(), session_scope=lambda: nullcontext(db))
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def headers_for(client: TestClient, seeded: SeedReport) -> Callable[[str], dict[str, str]]:
    """Authorization headers for a seeded user, picked by code (e.g. u-sup-01)."""

    def make(code: str) -> dict[str, str]:
        user_id = seed_id("taman-simulasi", "user", code)
        token = client.post("/api/v1/session", json={"user_id": str(user_id)}).json()["token"]
        return {"Authorization": f"Bearer {token}"}

    return make
