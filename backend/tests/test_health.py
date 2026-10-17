from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.db.session import get_db


def test_health_ok(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok"}


class _DownSession:
    def execute(self, *args: Any, **kwargs: Any) -> None:
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))


def test_health_reports_db_down(client: TestClient) -> None:
    client.app.dependency_overrides[get_db] = lambda: _DownSession()
    response = client.get("/api/v1/health")
    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "db": "down"}
