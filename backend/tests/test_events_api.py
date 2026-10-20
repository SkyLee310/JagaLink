"""M2.3: POST /events stores a valid batch in the one contract and refuses anything else."""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import ScenarioRun
from app.db.seed import SeedReport, seed_id

T0 = datetime(2026, 10, 21, 18, 10, tzinfo=UTC)
Headers = Callable[[str], dict[str, str]]


def node(code: str) -> str:
    return str(seed_id("taman-simulasi", "node", code))


@pytest.fixture
def run(db: Session, seeded: SeedReport) -> ScenarioRun:
    row = ScenarioRun(
        community_id=seeded.community_id,
        scenario_id=seed_id("taman-simulasi", "scenario", "s2-night-fence"),
        mode="live",
        speed=10,
        state="ready",
    )
    db.add(row)
    db.flush()
    return row


def event(run: ScenarioRun, seconds: float = 0, **changes: Any) -> dict[str, Any]:
    body = {
        "run_id": str(run.id),
        "ts": (T0 + timedelta(seconds=seconds)).isoformat(),
        "node_id": node("s-fence-n"),
        "type": "appear",
        "object_class": "person",
        "local_track_id": "s-fence-n#1",
        "attrs": {},
        "source": "sim",
    }
    return body | changes


def post(client: TestClient, headers_for: Headers, *events: dict[str, Any]) -> Any:
    return client.post(
        "/api/v1/events", json={"events": list(events)}, headers=headers_for("u-sup-01")
    )


def test_a_valid_batch_is_stored_in_order_and_read_back(
    client: TestClient, headers_for: Headers, run: ScenarioRun
) -> None:
    batch = [
        event(run, 0),
        event(run, 4, type="disappear"),
        event(run, 19.5, node_id=node("c-back-02"), local_track_id="c-back-02#1"),
    ]
    response = post(client, headers_for, *batch)
    assert response.status_code == 201
    stored = response.json()
    assert [item["seq"] for item in stored] == [1, 2, 3]
    assert stored[0]["ts"] == "2026-10-21T18:10:00.000Z"

    read = client.get(
        "/api/v1/events", params={"run_id": str(run.id)}, headers=headers_for("u-guard-01")
    )
    assert read.status_code == 200
    assert read.json() == stored

    at_back = client.get(
        "/api/v1/events",
        params={"run_id": str(run.id), "node_id": node("c-back-02")},
        headers=headers_for("u-guard-01"),
    )
    assert [item["seq"] for item in at_back.json()] == [3]
    window = client.get(
        "/api/v1/events",
        params={"from": "2026-10-21T18:10:04Z", "to": "2026-10-21T18:10:19.500Z"},
        headers=headers_for("u-guard-01"),
    )
    assert [item["seq"] for item in window.json()] == [2]


@pytest.mark.parametrize(
    "changes",
    [
        {"face_id": "x"},  # an unknown field
        {"ts": "2026-10-21T18:10:00"},  # no time zone
        {"type": "enter"},
        {"object_class": "dog"},
        {"source": "camera"},
        {"local_track_id": ""},
        {"attrs": {"plate_number": "ABC123"}},  # identity in attrs (D-10)
        {"attrs": {"note": "x" * 65}},
    ],
)
def test_a_malformed_event_is_refused_whole(
    client: TestClient, headers_for: Headers, run: ScenarioRun, changes: dict[str, Any]
) -> None:
    response = post(client, headers_for, event(run, 0), event(run, 1, **changes))
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    count = client.get(
        "/api/v1/events", params={"run_id": str(run.id)}, headers=headers_for("u-sup-01")
    )
    assert count.json() == []


def test_events_must_keep_time_order_across_batches(
    client: TestClient, headers_for: Headers, run: ScenarioRun
) -> None:
    assert post(client, headers_for, event(run, 10)).status_code == 201
    response = post(client, headers_for, event(run, 9))
    assert response.status_code == 422
    assert response.json()["code"] == "out_of_order"


def test_a_node_outside_the_community_is_refused(
    client: TestClient, headers_for: Headers, run: ScenarioRun
) -> None:
    response = post(client, headers_for, event(run, 0, node_id=str(uuid.uuid4())))
    assert response.status_code == 422
    assert response.json()["code"] == "unknown_node"


def test_one_batch_names_one_run(
    client: TestClient, headers_for: Headers, run: ScenarioRun
) -> None:
    other = event(run, 1, run_id=str(uuid.uuid4()))
    response = post(client, headers_for, event(run, 0), other)
    assert response.status_code == 422
    assert response.json()["code"] == "mixed_runs"


def test_an_unknown_run_is_404_and_a_closed_run_is_409(
    client: TestClient, headers_for: Headers, run: ScenarioRun, db: Session
) -> None:
    unknown = post(client, headers_for, event(run, 0, run_id=str(uuid.uuid4())))
    assert unknown.status_code == 404
    assert unknown.json()["code"] == "run_not_found"
    run.state = "finished"
    db.flush()
    closed = post(client, headers_for, event(run, 0))
    assert closed.status_code == 409
    assert closed.json()["code"] == "run_closed"


def test_only_a_supervisor_posts_events(
    client: TestClient, headers_for: Headers, run: ScenarioRun
) -> None:
    response = client.post(
        "/api/v1/events", json={"events": [event(run)]}, headers=headers_for("u-guard-01")
    )
    assert response.status_code == 403
    assert client.post("/api/v1/events", json={"events": [event(run)]}).status_code == 401
