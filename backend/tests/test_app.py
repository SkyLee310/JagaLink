import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.settings import get_settings
from app.main import create_app

OPENAPI_FILE = Path(__file__).resolve().parents[1] / "openapi.json"


def preflight(client: TestClient, origin: str):
    headers = {"Origin": origin, "Access-Control-Request-Method": "GET"}
    return client.options("/api/v1/health", headers=headers)


def test_unknown_route_uses_the_error_body(client: TestClient) -> None:
    response = client.get("/api/v1/no-such-route")
    assert response.status_code == 404
    assert response.json() == {"code": "not_found", "message": "Not Found", "details": None}


def test_cors_allows_the_frontend_origin(client: TestClient) -> None:
    origin = get_settings().frontend_origin
    response = preflight(client, origin)
    assert response.headers["access-control-allow-origin"] == origin


def test_cors_ignores_other_origins(client: TestClient) -> None:
    response = preflight(client, "https://elsewhere.example")
    assert "access-control-allow-origin" not in response.headers


def test_unexpected_errors_use_the_error_body() -> None:
    app = create_app()

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("kaboom")

    response = TestClient(app, raise_server_exceptions=False).get("/boom")
    assert response.status_code == 500
    assert response.json() == {
        "code": "internal_error",
        "message": "Something went wrong on the server",
        "details": None,
    }


def test_committed_openapi_matches_the_app() -> None:
    committed = json.loads(OPENAPI_FILE.read_text(encoding="utf-8"))
    current = json.loads(json.dumps(create_app().openapi()))
    assert current == committed, "backend/openapi.json is stale: run make types (D-42)"
