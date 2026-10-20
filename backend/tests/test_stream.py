"""M2.5, M3.3: GET /stream sends a run's events and track updates as Server-Sent Events."""

import asyncio
import json
import uuid
from collections.abc import Callable

from fastapi.testclient import TestClient

from app.db.seed import seed_id
from app.sim.runs import RunManager
from tests.fakes import InstantTimer

Headers = Callable[[str], dict[str, str]]
S2 = str(seed_id("taman-simulasi", "scenario", "s2-night-fence"))


def test_the_stream_sends_the_backlog_and_ends_when_the_run_is_reset(
    client: TestClient, headers_for: Headers
) -> None:
    manager: RunManager = client.app.state.runs  # type: ignore[attr-defined]
    manager.timer = InstantTimer()
    sup = headers_for("u-sup-01")
    run = client.post("/api/v1/scenario-runs", json={"scenario_id": S2}, headers=sup).json()
    run_id = uuid.UUID(run["id"])
    client.portal.call(manager.wait, run_id)  # type: ignore[union-attr]

    async def close_once_subscribed() -> None:
        while not (channel := manager.hub.channel(run_id)) or not channel.queues:
            await asyncio.sleep(0.01)
        manager.hub.close(run_id)

    client.portal.start_task_soon(close_once_subscribed)  # type: ignore[union-attr]
    response = client.get(
        "/api/v1/stream", params={"run_id": run["id"]}, headers=headers_for("u-guard-03")
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"
    frames = [frame.split("\n") for frame in response.text.split("\n\n") if frame]
    kinds = [frame[1] for frame in frames]
    assert kinds.count("event: event") == 15
    assert frames[0][:2] == ["id: 1", "event: event"]
    assert frames[0][2].startswith('data: {"id":')
    assert '"type":"appear"' in frames[0][2]
    # The person's path grows with each sighting and closes when the window ends.
    assert kinds[-1] == "event: track_update"
    path = json.loads(frames[-1][2].removeprefix("data: "))
    assert (path["status"], len(path["segments"])) == ("closed", 6)


def test_a_new_subscriber_after_a_restart_gets_the_backlog_from_the_database(
    client: TestClient, headers_for: Headers
) -> None:
    manager: RunManager = client.app.state.runs  # type: ignore[attr-defined]
    manager.timer = InstantTimer()
    sup = headers_for("u-sup-01")
    run = client.post("/api/v1/scenario-runs", json={"scenario_id": S2}, headers=sup).json()
    client.portal.call(manager.wait, uuid.UUID(run["id"]))  # type: ignore[union-attr]
    community_id = seed_id("taman-simulasi", "community")

    backlog = manager.backlog(uuid.UUID(run["id"]), community_id)

    kinds = [kind for kind, _ in backlog]
    assert kinds == ["event"] * 15 + ["track_update"] + ["alert_update"] * 3
    assert [data["seq"] for _, data in backlog[:15]] == list(range(1, 16))
    path = backlog[15][1]
    assert (path["status"], len(path["segments"])) == ("closed", 6)
    # The run's alerts, oldest first; they are not new to a late subscriber.
    alerts = [data for _, data in backlog[16:]]
    assert [alert["rule"] for alert in alerts] == ["after_hours", "off_route", "loiter"]
    assert {alert["track_id"] for alert in alerts} == {path["id"]}


def test_the_stream_needs_a_token_and_a_run_of_the_community(
    client: TestClient, headers_for: Headers
) -> None:
    unknown = str(uuid.uuid4())
    assert client.get("/api/v1/stream", params={"run_id": unknown}).status_code == 401
    missing = client.get(
        "/api/v1/stream", params={"run_id": unknown}, headers=headers_for("u-guard-01")
    )
    assert (missing.status_code, missing.json()["code"]) == (404, "run_not_found")
