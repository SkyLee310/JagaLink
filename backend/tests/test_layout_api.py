from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy.orm import Session

from app.core.auth import issue_token
from app.core.settings import get_settings
from app.db.models import AppUser, Community
from app.db.seed import SeedReport, seed_id


def token_for(client: TestClient, code: str = "u-guard-02") -> str:
    user_id = seed_id("taman-simulasi", "user", code)
    return client.post("/api/v1/session", json={"user_id": str(user_id)}).json()["token"]


def get_layout(client: TestClient, community_id: UUID, token: str | None = None) -> Response:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return client.get(f"/api/v1/communities/{community_id}/layout", headers=headers)


def test_layout_needs_a_token(client: TestClient, seeded: SeedReport) -> None:
    response = get_layout(client, seeded.community_id)
    assert response.status_code == 401
    assert response.json() == {
        "code": "unauthorized",
        "message": "Send the session token as a bearer token",
        "details": None,
    }


@pytest.mark.parametrize("code", ["u-guard-02", "u-sup-01"])
def test_layout_of_own_community(client: TestClient, seeded: SeedReport, code: str) -> None:
    response = get_layout(client, seeded.community_id, token_for(client, code))
    assert response.status_code == 200
    layout = response.json()
    assert layout["community"]["id"] == str(seeded.community_id)
    assert layout["community"]["scale_m_per_px"] == 0.25
    assert (len(layout["zones"]), len(layout["nodes"]), len(layout["links"])) == (6, 20, 23)

    nodes = {node["code"]: node for node in layout["nodes"]}
    assert (nodes["c-gate-01"]["x"], nodes["c-gate-01"]["y"]) == (90, 380)
    node_ids = {node["id"] for node in layout["nodes"]}
    assert all({link["from_node_id"], link["to_node_id"]} <= node_ids for link in layout["links"])
    assert all(len(point) == 2 for zone in layout["zones"] for point in zone["polygon"])


def test_layout_of_another_community_is_forbidden(
    client: TestClient, db: Session, seeded: SeedReport
) -> None:
    other = Community(code="taman-lain", name="Taman Lain", scale_m_per_px=0.5)
    db.add(other)
    db.flush()
    response = get_layout(client, other.id, token_for(client))
    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


def test_unknown_community_is_not_found(client: TestClient, seeded: SeedReport) -> None:
    response = get_layout(client, uuid4(), token_for(client))
    assert response.status_code == 404
    assert response.json()["code"] == "community_not_found"


def test_forged_token_is_rejected(client: TestClient, seeded: SeedReport) -> None:
    payload = token_for(client).split(".")[0]
    response = get_layout(client, seeded.community_id, f"{payload}.forged")
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_token"


def test_token_for_a_missing_user_is_rejected(client: TestClient, seeded: SeedReport) -> None:
    ghost = AppUser(
        id=uuid4(), community_id=seeded.community_id, code="u-ghost", name="Ghost", role="guard"
    )
    token, _ = issue_token(ghost, datetime.now(UTC), get_settings().session_secret)
    response = get_layout(client, seeded.community_id, token)
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_token"
