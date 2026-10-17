from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.auth import verify_token
from app.core.settings import get_settings
from app.db.seed import SeedReport, seed_id

GUARD_B = seed_id("taman-simulasi", "user", "u-guard-02")


def test_lists_the_seeded_users(client: TestClient, seeded: SeedReport) -> None:
    response = client.get("/api/v1/session/users")
    assert response.status_code == 200
    assert [(user["code"], user["role"]) for user in response.json()] == [
        ("u-guard-01", "guard"),
        ("u-guard-02", "guard"),
        ("u-guard-03", "guard"),
        ("u-sup-01", "supervisor"),
    ]


def test_session_for_a_seeded_user(client: TestClient, seeded: SeedReport) -> None:
    response = client.post("/api/v1/session", json={"user_id": str(GUARD_B)})
    assert response.status_code == 200
    body = response.json()
    assert body["user"] == {
        "id": str(GUARD_B),
        "code": "u-guard-02",
        "name": "Guard B",
        "role": "guard",
        "on_duty": True,
    }
    assert body["community_id"] == str(seeded.community_id)
    assert body["expires_at"].endswith(".000Z")
    claims = verify_token(body["token"], datetime.now(UTC), get_settings().session_secret)
    assert (claims.user_id, claims.role) == (GUARD_B, "guard")
    assert claims.expires_at == datetime.fromisoformat(body["expires_at"])


def test_unknown_user_is_not_found(client: TestClient, seeded: SeedReport) -> None:
    response = client.post("/api/v1/session", json={"user_id": str(uuid4())})
    assert response.status_code == 404
    assert response.json() == {
        "code": "user_not_found",
        "message": "No seeded user has that ID",
        "details": None,
    }


def test_malformed_body_is_rejected(client: TestClient) -> None:
    response = client.post("/api/v1/session", json={"user_id": "not-a-uuid"})
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
