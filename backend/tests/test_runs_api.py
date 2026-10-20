"""M2.4: scenario runs start, pause, resume and reset; one live run per community (D-77)."""

import json
import uuid
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import AppUser, Link, ScenarioRun
from app.db.seed import SeedReport, seed_id
from app.sim.golden import event_line, seeded_scripts
from app.sim.runs import RunManager
from tests.fakes import InstantTimer

Headers = Callable[[str], dict[str, str]]
Json = dict[str, Any]
S1 = str(seed_id("taman-simulasi", "scenario", "s1-evening-vehicle"))
S2 = str(seed_id("taman-simulasi", "scenario", "s2-night-fence"))


def node_id(code: str) -> uuid.UUID:
    return seed_id("taman-simulasi", "node", code)


@pytest.fixture
def sup(headers_for: Headers) -> dict[str, str]:
    return headers_for("u-sup-01")


def manager(client: TestClient) -> RunManager:
    return client.app.state.runs  # type: ignore[attr-defined,no-any-return]


def start(client: TestClient, sup: dict[str, str], scenario: str, **body: Any) -> Json:
    response = client.post(
        "/api/v1/scenario-runs", json={"scenario_id": scenario, **body}, headers=sup
    )
    assert response.status_code == 201, response.text
    return response.json()  # type: ignore[no-any-return]


def control(client: TestClient, headers: dict[str, str], run: Json, action: str) -> Any:
    return client.post(f"/api/v1/scenario-runs/{run['id']}/{action}", headers=headers)


def wait_for_end(client: TestClient, run: Json) -> None:
    client.portal.call(manager(client).wait, uuid.UUID(run["id"]))  # type: ignore[union-attr]


def posted(client: TestClient, sup: dict[str, str], run: Json) -> list[Json]:
    params = {"run_id": run["id"], "limit": 5000}
    return client.get("/api/v1/events", params=params, headers=sup).json()  # type: ignore[no-any-return]


def test_scenarios_list_their_live_window_and_no_truth(
    client: TestClient, sup: dict[str, str], headers_for: Headers
) -> None:
    response = client.get("/api/v1/scenarios", headers=sup)
    assert response.status_code == 200
    s1, s2 = response.json()
    assert (s1["code"], s1["duration_s"], s1["default_speed"]) == ("s1-evening-vehicle", 840, 10)
    assert (s1["window_start"], s1["window_end"]) == (
        "2026-10-21T11:18:00.000Z",
        "2026-10-21T11:32:00.000Z",
    )
    assert s2["code"] == "s2-night-fence"
    assert set(s2) == {
        "id",
        "code",
        "name",
        "description",
        "duration_s",
        "default_speed",
        "window_start",
        "window_end",
    }
    assert client.get("/api/v1/scenarios", headers=headers_for("u-guard-01")).status_code == 403


def test_start_places_the_roster_and_becomes_current(
    client: TestClient, sup: dict[str, str], headers_for: Headers, db: Session
) -> None:
    run = start(client, sup, S2)
    assert run["state"] == "playing"
    assert (run["speed"], run["events_emitted"], run["events_total"]) == (10, 0, 15)
    assert run["clock"] == run["window_start"] == "2026-10-21T18:08:00.000Z"

    current = client.get("/api/v1/scenario-runs/current", headers=headers_for("u-guard-02"))
    assert current.json()["id"] == run["id"]
    guards = {
        user.code: (user.on_duty, user.current_node_id)
        for user in db.scalars(select(AppUser).where(AppUser.role == "guard"))
    }
    assert guards == {
        "u-guard-01": (True, node_id("c-gate-01")),
        "u-guard-02": (False, None),
        "u-guard-03": (True, node_id("c-main-03")),
    }


def test_no_run_yet_means_no_current_run(client: TestClient, sup: dict[str, str]) -> None:
    response = client.get("/api/v1/scenario-runs/current", headers=sup)
    assert (response.status_code, response.json()) == (200, None)


def test_pause_resume_and_reset_move_the_run_through_its_states(
    client: TestClient, sup: dict[str, str]
) -> None:
    run = start(client, sup, S1, speed=30)
    assert run["speed"] == 30

    assert control(client, sup, run, "pause").json()["state"] == "paused"
    again = control(client, sup, run, "pause")
    assert (again.status_code, again.json()["code"]) == (409, "run_not_playing")

    resumed = client.post(
        f"/api/v1/scenario-runs/{run['id']}/resume", json={"speed": 60}, headers=sup
    )
    assert (resumed.json()["state"], resumed.json()["speed"]) == ("playing", 60)

    reset = control(client, sup, run, "reset").json()
    assert (reset["state"], reset["clock"]) == ("ready", run["window_start"])
    assert control(client, sup, run, "resume").json()["state"] == "playing"


def test_a_new_run_stops_the_previous_one(
    client: TestClient, sup: dict[str, str], db: Session
) -> None:
    first = start(client, sup, S1)
    second = start(client, sup, S2)
    states = {
        str(key): value for key, value in db.execute(select(ScenarioRun.id, ScenarioRun.state))
    }
    assert states == {first["id"]: "stopped", second["id"]: "playing"}
    stopped = control(client, sup, first, "resume")
    assert (stopped.status_code, stopped.json()["code"]) == (409, "run_closed")


@pytest.mark.parametrize("code", ["s1-evening-vehicle", "s2-night-fence"])
def test_a_run_posts_its_live_window_and_a_reset_replays_it_identically(
    client: TestClient, sup: dict[str, str], code: str
) -> None:
    manager(client).timer = InstantTimer()
    run = start(client, sup, str(seed_id("taman-simulasi", "scenario", code)))
    wait_for_end(client, run)

    finished = client.get(f"/api/v1/scenario-runs/{run['id']}", headers=sup).json()
    assert finished["state"] == "finished"
    assert finished["clock"] == finished["window_end"]
    assert finished["events_emitted"] == finished["events_total"]

    first = posted(client, sup, run)
    live = seeded_scripts()[code].live_events()
    codes = {str(node_id(event.node)): event.node for event in live}
    contract = [
        [
            item["ts"],
            codes[item["node_id"]],
            item["type"],
            item["object_class"],
            item["local_track_id"],
        ]
        for item in first
    ]
    assert contract == [json.loads(event_line(event))[:5] for event in live]
    assert {item["source"] for item in first} == {"sim"}
    assert all(item["attrs"] == {} for item in first)

    control(client, sup, run, "reset")
    assert posted(client, sup, run) == []
    control(client, sup, run, "resume")
    wait_for_end(client, run)
    second = posted(client, sup, run)
    assert [item | {"id": None} for item in second] == [item | {"id": None} for item in first]


def test_a_scenario_that_no_longer_fits_is_refused(
    client: TestClient, sup: dict[str, str], db: Session
) -> None:
    back, lane = node_id("c-back-02"), node_id("c-lane-2n")
    db.execute(
        delete(Link).where(
            ((Link.from_node_id == back) & (Link.to_node_id == lane))
            | ((Link.from_node_id == lane) & (Link.to_node_id == back))
        )
    )
    db.flush()
    response = client.post("/api/v1/scenario-runs", json={"scenario_id": S2}, headers=sup)
    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "scenario_does_not_fit"
    assert "t1 visit 2: no link c-back-02 -> c-lane-2n" in body["details"]


def test_run_control_is_for_supervisors_in_the_community(
    client: TestClient, sup: dict[str, str], headers_for: Headers, seeded: SeedReport
) -> None:
    run = start(client, sup, S1)
    assert control(client, headers_for("u-guard-01"), run, "pause").status_code == 403
    missing = client.post(f"/api/v1/scenario-runs/{seeded.community_id}/pause", headers=sup)
    assert (missing.status_code, missing.json()["code"]) == (404, "run_not_found")
    unknown = client.post(
        "/api/v1/scenario-runs", json={"scenario_id": str(seeded.community_id)}, headers=sup
    )
    assert (unknown.status_code, unknown.json()["code"]) == (404, "scenario_not_found")
    eval_mode = client.post(
        "/api/v1/scenario-runs", json={"scenario_id": S1, "mode": "eval"}, headers=sup
    )
    assert eval_mode.status_code == 422


def test_a_restart_leaves_a_playing_run_paused_and_resumable(
    client: TestClient, sup: dict[str, str]
) -> None:
    run = start(client, sup, S2)
    old = manager(client)
    client.portal.call(old.shutdown)  # type: ignore[union-attr]
    assert old.loop is not None
    fresh = RunManager(timer=InstantTimer(), session_scope=old.session_scope)
    fresh.bind(old.loop)
    client.app.state.runs = fresh  # type: ignore[attr-defined]

    current = client.get("/api/v1/scenario-runs/current", headers=sup).json()
    assert current["state"] == "paused"
    assert control(client, sup, run, "resume").json()["state"] == "playing"
    wait_for_end(client, run)
    assert len(posted(client, sup, run)) == 15
