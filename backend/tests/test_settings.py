import pytest
from pydantic import ValidationError

from app.core.settings import DEV_SESSION_SECRET, Settings


def make(**values: str) -> Settings:
    return Settings(_env_file=None, **values)


@pytest.mark.parametrize("url", ["postgres://u:p@db:5432/app", "postgresql://u:p@db:5432/app"])
def test_database_url_normalised(url: str) -> None:
    assert make(database_url=url).database_url == "postgresql+psycopg://u:p@db:5432/app"


def test_psycopg_url_left_alone() -> None:
    url = "postgresql+psycopg://u:p@db:5432/app"
    assert make(database_url=url).database_url == url


def test_frontend_origin_drops_trailing_slash() -> None:
    origin = make(frontend_origin="https://jagalink.vercel.app/").frontend_origin
    assert origin == "https://jagalink.vercel.app"


def test_prod_refuses_the_dev_secret() -> None:
    with pytest.raises(ValidationError, match="SESSION_SECRET"):
        make(app_env="prod", session_secret=DEV_SESSION_SECRET)


def test_prod_refuses_a_short_secret() -> None:
    with pytest.raises(ValidationError, match="SESSION_SECRET"):
        make(app_env="prod", session_secret="too-short")


def test_prod_accepts_a_long_secret() -> None:
    assert make(app_env="prod", session_secret="x" * 48).app_env == "prod"
