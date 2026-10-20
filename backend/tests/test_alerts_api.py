"""M4.2, M4.4, M4.6: alerts reach the stream and the API with their rule, guard and next camera;
guards confirm or dismiss them once; thresholds changed through the API change the outcome."""

import asyncio
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.db.alert_store import alert_id
from app.db.models import AppUser, ScenarioRun
from app.db.seed import SeedReport, seed_id
from app.db.track_store import track_id
from app.sim.golden import seeded_layout
from app.sim.runs import RunManager
from tests.fakes import InstantTimer

Headers = Callable[[str], dict[str, str]]
Json = dict[str, Any]
S2 = str(seed_id("taman-simulasi", "scenario", "s2-night-fence"))
T0 = datetime(2026, 10, 21, 18, 10, tzinfo=UTC)  # 02:10 in Kuala Lumpur: quiet hours


def node(code: str) -> str:
    return str(seed_id("taman-simulasi", "node", code))


CODES = {node(code): code for code in seeded_layout().node_codes}


def manager_of(client: TestClient) -> RunManager:
    return client.app.state.runs  # type: ignore[attr-defined,no-any-return]


def play_s2(client: TestClient, headers_for: Headers) -> uuid.UUID:
    manager = manager_of(client)
    manager.timer = InstantTimer()
    run = client.post(
        "/api/v1/scenario-runs", json={"scenario_id": S2}, headers=headers_for("u-sup-01")
    ).json()
    run_id = uuid.UUID(run["id"])
    client.portal.call(manager.wait, run_id)  # type: ignore[union-attr]
    return run_id


def alerts(client: TestClient, headers: dict[str, str], run_id: uuid.UUID) -> list[Json]:
    response = client.get("/api/v1/alerts", params={"run_id": str(run_id)}, headers=headers)
    assert response.status_code == 200
    return response.json()  # type: ignore[no-any-return]


def act(client: TestClient, headers: dict[str, str], alert: str, body: Json) -> Any:
    return client.post(f"/api/v1/alerts/{alert}/actions", json=body, headers=headers)


def stream_alerts(client: TestClient, run_id: uuid.UUID) -> list[tuple[str, Json]]:
    """The run's `alert` and `alert_update` messages so far, once the loop has published."""
    client.portal.call(asyncio.sleep, 0)  # type: ignore[union-attr]
    channel = manager_of(client).hub.channel(run_id)
    assert channel is not None
    return [(m.type, m.data) for m in channel.log if m.type in ("alert", "alert_update")]


def test_a_played_run_raises_its_alerts_on_the_stream_and_the_api(
    client: TestClient, headers_for: Headers
) -> None:
    run_id = play_s2(client, headers_for)
    guard = headers_for("u-guard-03")
    found = alerts(client, guard, run_id)

    assert [alert["rule"] for alert in found] == ["after_hours", "off_route", "loiter"]
    assert [alert["created_ts"] for alert in found] == [
        "2026-10-21T18:10:00.000Z",
        "2026-10-21T18:10:19.500Z",
        "2026-10-21T18:13:56.500Z",
    ]
    reason = (
        "Rule-based: 3 rules matched this path (after-hours entry, loitering, off-route movement)."
    )
    events = client.get("/api/v1/events", params={"run_id": str(run_id)}, headers=guard).json()
    for alert in found:
        assert alert["id"] == str(alert_id(run_id, 1, alert["rule"]))
        assert (alert["status"], alert["severity"], alert["triage_status"]) == (
            "new",
            "high",
            "pending",
        )
        assert alert["severity_reason"] == reason
        assert alert["assigned_user"]["code"] == "u-guard-03"
        assert alert["track_id"] == str(track_id(run_id, 1))
        assert alert["track_anon_id"].startswith("obj-")
        assert set(alert["evidence_event_ids"]) <= {event["id"] for event in events}
    assert [alert["walk_s"] for alert in found] == [115.5, 100.0, 69.0]
    assert client.get(f"/api/v1/alerts/{found[0]['id']}", headers=guard).json() == found[0]

    # Each alert opened once, as the guard first saw it; repeat matches updated it (D-59).
    messages = stream_alerts(client, run_id)
    opened = [data for kind, data in messages if kind == "alert"]
    assert [
        (
            alert["rule"],
            CODES[alert["node_id"]],
            alert["severity"],
            alert["walk_s"],
            CODES[alert["next_node"]["id"]],
        )
        for alert in opened
    ] == [
        ("after_hours", "s-fence-n", "medium", 115.5, "c-back-02"),
        ("off_route", "c-back-02", "high", 100.0, "c-lane-2n"),
        ("loiter", "c-lane-2n", "high", 69.0, "c-main-02"),
    ]
    assert opened[0]["severity_reason"] == "Rule-based: after-hours entry is rated medium."
    basis = opened[0]["next_node"]["basis"]
    assert basis["walk_s"] == 15.5  # s-fence-n → c-back-02 takes 14-17 s
    assert set(basis) == {
        "walk_s",
        "distance_m",
        "transition_share",
        "direction",
        "backtrack",
        "score",
    }
    versions: dict[str, list[int]] = {}
    for _, data in messages:
        versions.setdefault(data["id"], []).append(data["version"])
    assert all(seen == list(range(1, len(seen) + 1)) for seen in versions.values())
    assert {data["id"]: data for _, data in messages} == {alert["id"]: alert for alert in found}


def test_a_guard_confirms_or_dismisses_once_and_every_screen_hears_of_it(
    client: TestClient, headers_for: Headers
) -> None:
    run_id = play_s2(client, headers_for)
    first, second, _ = alerts(client, headers_for("u-guard-03"), run_id)

    body = {"action": "confirm", "reason": "  Seen on c-back-02, going now  "}
    confirmed = act(client, headers_for("u-guard-03"), first["id"], body)
    assert confirmed.status_code == 200
    out = confirmed.json()
    assert (out["status"], out["version"]) == ("acked", first["version"] + 1)
    # The run has finished, so its clock rests at the end of the live window.
    assert out["acked_ts"] == "2026-10-21T18:18:00.000Z"
    [action] = out["actions"]
    assert (action["action"], action["reason"], action["ts"], action["user"]["code"]) == (
        "confirm",
        "Seen on c-back-02, going now",
        "2026-10-21T18:18:00.000Z",
        "u-guard-03",
    )

    again = act(client, headers_for("u-guard-01"), first["id"], {"action": "dismiss"})
    assert (again.status_code, again.json()["code"]) == (409, "alert_already_handled")
    dismissed = act(client, headers_for("u-sup-01"), second["id"], {"action": "dismiss"})
    assert (dismissed.json()["status"], dismissed.json()["actions"][0]["reason"]) == (
        "dismissed",
        "",
    )

    updates = [data for kind, data in stream_alerts(client, run_id) if kind == "alert_update"]
    assert [(data["id"], data["status"]) for data in updates[-2:]] == [
        (first["id"], "acked"),
        (second["id"], "dismissed"),
    ]


@pytest.mark.parametrize(
    "body",
    [
        {"action": "confirm", "reason": "first line\nsecond line"},
        {"action": "confirm", "reason": "x" * 201},
        {"action": "escalate"},
        {},
    ],
)
def test_an_action_is_one_click_with_a_one_line_reason(
    client: TestClient, headers_for: Headers, body: Json
) -> None:
    run_id = play_s2(client, headers_for)
    [first, *_] = alerts(client, headers_for("u-guard-03"), run_id)
    response = act(client, headers_for("u-guard-03"), first["id"], body)
    assert (response.status_code, response.json()["code"]) == (422, "validation_error")


def test_alerts_need_a_token_and_an_id_in_the_community(
    client: TestClient, headers_for: Headers
) -> None:
    assert client.get("/api/v1/alerts").status_code == 401
    unknown = str(uuid.uuid4())
    guard = headers_for("u-guard-01")
    for response in (
        client.get(f"/api/v1/alerts/{unknown}", headers=guard),
        act(client, guard, unknown, {"action": "confirm"}),
    ):
        assert (response.status_code, response.json()["code"]) == (404, "alert_not_found")


def test_reset_clears_the_runs_alerts(client: TestClient, headers_for: Headers) -> None:
    run_id = play_s2(client, headers_for)
    sup = headers_for("u-sup-01")
    assert client.post(f"/api/v1/scenario-runs/{run_id}/reset", headers=sup).status_code == 200
    assert alerts(client, sup, run_id) == []


# Events posted straight to a run ---------------------------------------------------------------


@pytest.fixture
def run(db: Session, seeded: SeedReport) -> ScenarioRun:
    row = ScenarioRun(
        community_id=seeded.community_id,
        scenario_id=uuid.UUID(S2),
        mode="live",
        speed=10,
        state="ready",
    )
    db.add(row)
    db.flush()
    return row


def stay(run: ScenarioRun, code: str, start: float, end: float, local: str) -> list[Json]:
    def event(seconds: float, kind: str) -> Json:
        return {
            "run_id": str(run.id),
            "ts": (T0 + timedelta(seconds=seconds)).isoformat(),
            "node_id": node(code),
            "type": kind,
            "object_class": "person",
            "local_track_id": local,
            "attrs": {},
            "source": "video",
        }

    return [event(start, "appear"), event(end, "disappear")]


def post(client: TestClient, headers_for: Headers, events: list[Json]) -> None:
    response = client.post(
        "/api/v1/events", json={"events": events}, headers=headers_for("u-sup-01")
    )
    assert response.status_code == 201


def test_a_threshold_changed_through_the_api_changes_the_outcome(
    client: TestClient, headers_for: Headers, run: ScenarioRun
) -> None:
    sup = headers_for("u-sup-01")
    # 100 s on the main road: under the 180 s loitering threshold, and no lane after hours.
    post(client, headers_for, stay(run, "c-main-02", 0, 100, "m#1"))
    assert alerts(client, sup, run.id) == []

    lower = client.put("/api/v1/rules/loiter", json={"params": {"threshold_s": 60}}, headers=sup)
    assert lower.status_code == 200
    post(client, headers_for, stay(run, "c-main-02", 200, 300, "m#2"))

    [alert] = alerts(client, sup, run.id)
    assert (alert["rule"], alert["score"], alert["created_ts"]) == (
        "loiter",
        100.0,
        "2026-10-21T18:15:00.000Z",
    )
    assert alert["detail"] == "100 s in zone z-main within 10 min (threshold 60 s)."


def test_a_rules_own_severity_comes_from_its_config(
    client: TestClient, headers_for: Headers, run: ScenarioRun
) -> None:
    sup = headers_for("u-sup-01")
    body = {"params": {"severity": "low"}}
    assert client.put("/api/v1/rules/after_hours", json=body, headers=sup).status_code == 200
    post(client, headers_for, stay(run, "s-fence-n", 0, 4, "n#1"))

    [alert] = alerts(client, sup, run.id)
    assert (alert["rule"], alert["severity"]) == ("after_hours", "low")
    assert alert["severity_reason"] == "Rule-based: after-hours entry is rated low."


def test_with_nobody_on_duty_an_alert_escalates_to_the_supervisor(
    client: TestClient, headers_for: Headers, run: ScenarioRun, db: Session
) -> None:
    db.execute(update(AppUser).where(AppUser.role == "guard").values(on_duty=False))
    db.flush()
    post(client, headers_for, stay(run, "s-fence-n", 0, 4, "n#1"))

    [alert] = alerts(client, headers_for("u-sup-01"), run.id)
    assert (alert["rule"], alert["status"], alert["walk_s"]) == ("after_hours", "escalated", None)
    assert alert["assigned_user"]["code"] == "u-sup-01"
    confirmed = act(client, headers_for("u-sup-01"), alert["id"], {"action": "confirm"})
    assert confirmed.json()["status"] == "acked"


def test_after_a_restart_a_repeat_match_updates_the_stored_alert(
    client: TestClient, headers_for: Headers, run: ScenarioRun
) -> None:
    post(client, headers_for, stay(run, "s-fence-n", 0, 4, "n#1"))
    # A restart loses the alerter; the next batch rebuilds it from the stored events.
    manager_of(client).pipelines.forget(run.id)
    post(client, headers_for, stay(run, "c-back-02", 19.5, 25.5, "b#1"))

    found = alerts(client, headers_for("u-sup-01"), run.id)
    assert [(a["rule"], a["version"], a["severity"]) for a in found] == [
        ("after_hours", 2, "high"),
        ("off_route", 1, "high"),
    ]
    assert len(found[0]["evidence_event_ids"]) == 2
