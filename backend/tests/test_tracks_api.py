"""M3.3, M3.5: stored events become tracks that read back with ordered segments, and expire."""

import re
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import ScenarioRun
from app.db.seed import SeedReport, seed_id
from app.db.track_store import track_id
from app.sim.runs import RunManager
from tests.fakes import InstantTimer

Headers = Callable[[str], dict[str, str]]
S2 = str(seed_id("taman-simulasi", "scenario", "s2-night-fence"))
S2_PATH = ["s-fence-n", "c-back-02", "c-lane-2n", "c-main-02", "c-lane-2s", "s-fence-s"]
T0 = datetime(2026, 10, 21, 18, 10, tzinfo=UTC)


def node(code: str) -> str:
    return str(seed_id("taman-simulasi", "node", code))


CODES = {node(code): code for code in [*S2_PATH, "c-gate-01", "c-park-01"]}


def play_s2(client: TestClient, headers_for: Headers) -> uuid.UUID:
    manager: RunManager = client.app.state.runs  # type: ignore[attr-defined]
    manager.timer = InstantTimer()
    run = client.post(
        "/api/v1/scenario-runs", json={"scenario_id": S2}, headers=headers_for("u-sup-01")
    ).json()
    run_id = uuid.UUID(run["id"])
    client.portal.call(manager.wait, run_id)  # type: ignore[union-attr]
    return run_id


def tracks(client: TestClient, headers: dict[str, str], run_id: uuid.UUID) -> list[Any]:
    response = client.get("/api/v1/tracks", params={"run_id": str(run_id)}, headers=headers)
    assert response.status_code == 200
    return response.json()


def test_a_played_run_links_the_person_into_one_track_with_ordered_segments(
    client: TestClient, headers_for: Headers
) -> None:
    run_id = play_s2(client, headers_for)
    guard = headers_for("u-guard-03")

    [path] = tracks(client, guard, run_id)
    assert re.fullmatch(r"obj-[0-9a-f]{6}", path["anon_id"])
    assert (path["status"], path["object_class"]) == ("closed", "person")
    assert [CODES[segment["node_id"]] for segment in path["segments"]] == S2_PATH
    enters = [segment["enter_ts"] for segment in path["segments"]]
    assert enters == sorted(enters)
    assert path["first_ts"] == "2026-10-21T18:10:00.000Z"
    assert path["last_ts"] == "2026-10-21T18:16:16.000Z"
    assert path["expires_at"] == "2026-10-22T18:16:16.000Z"

    one = client.get(f"/api/v1/tracks/{path['id']}", headers=guard)
    assert one.status_code == 200
    assert one.json() == path

    events = client.get("/api/v1/events", params={"run_id": str(run_id)}, headers=guard).json()
    linked = [event_id for segment in path["segments"] for event_id in segment["event_ids"]]
    assert linked == [event["id"] for event in events]


def test_reset_clears_the_runs_tracks(client: TestClient, headers_for: Headers) -> None:
    run_id = play_s2(client, headers_for)
    sup = headers_for("u-sup-01")
    assert client.post(f"/api/v1/scenario-runs/{run_id}/reset", headers=sup).status_code == 200
    assert tracks(client, sup, run_id) == []


def test_an_expired_track_is_purged_and_then_not_found(
    client: TestClient, headers_for: Headers
) -> None:
    manager: RunManager = client.app.state.runs  # type: ignore[attr-defined]
    manager.pipelines.ttl_s = 30
    run_id = play_s2(client, headers_for)
    guard = headers_for("u-guard-03")

    # The person was last seen at 02:16:16 and the window ends at 02:18: past the 30 s TTL.
    missing = client.get(f"/api/v1/tracks/{track_id(run_id, 1)}", headers=guard)
    assert (missing.status_code, missing.json()["code"]) == (404, "track_not_found")
    assert tracks(client, guard, run_id) == []
    channel = manager.hub.channel(run_id)
    assert channel is not None
    updates = [m.data for m in channel.log if m.type == "track_update"]
    assert updates[-1]["status"] == "expired"


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


def stay(run: ScenarioRun, code: str, start: float, end: float, local: str) -> list[Any]:
    def event(seconds: float, kind: str) -> dict[str, Any]:
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


def post(client: TestClient, headers_for: Headers, events: list[Any]) -> None:
    response = client.post(
        "/api/v1/events", json={"events": events}, headers=headers_for("u-sup-01")
    )
    assert response.status_code == 201


def test_posted_events_link_across_batches_and_a_restart(
    client: TestClient, headers_for: Headers, run: ScenarioRun
) -> None:
    manager: RunManager = client.app.state.runs  # type: ignore[attr-defined]
    post(client, headers_for, stay(run, "s-fence-n", 0, 4, "n#1"))
    # A restart loses the linker; the next batch rebuilds it from the stored events.
    manager.pipelines.forget(run.id)
    # s-fence-n → c-back-02 is a 14-17 s walk: 15.5 s after leaving joins the same track.
    post(client, headers_for, stay(run, "c-back-02", 19.5, 25.5, "b#1"))
    # c-gate-01 has no link from c-back-02: a new track.
    post(client, headers_for, stay(run, "c-gate-01", 40, 42, "g#1"))

    found = tracks(client, headers_for("u-guard-01"), run.id)
    assert [[CODES[s["node_id"]] for s in t["segments"]] for t in found] == [
        ["s-fence-n", "c-back-02"],
        ["c-gate-01"],
    ]
    assert found[0]["id"] == str(track_id(run.id, 1))


def test_tracks_need_a_token_and_an_id_in_the_community(
    client: TestClient, headers_for: Headers
) -> None:
    assert client.get("/api/v1/tracks").status_code == 401
    unknown = client.get(f"/api/v1/tracks/{uuid.uuid4()}", headers=headers_for("u-guard-01"))
    assert (unknown.status_code, unknown.json()["code"]) == (404, "track_not_found")
