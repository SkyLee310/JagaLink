"""M2.2: a scenario turns into the same ordered event list on every run (golden event files)."""

from collections import defaultdict

import pytest

from app.schemas.layout import LayoutFile
from app.sim.golden import LAYOUT_PATH, golden_path, render, seeded_scripts
from app.sim.scenario import EventRef, graph_from_layout
from app.sim.script import Script, ScriptEvent, to_ms

CODES = ["s1-evening-vehicle", "s2-night-fence"]


@pytest.fixture(scope="module")
def scripts() -> dict[str, Script]:
    return seeded_scripts()


@pytest.mark.parametrize("code", CODES)
def test_two_builds_give_the_identical_golden_sequence(
    scripts: dict[str, Script], code: str
) -> None:
    again = seeded_scripts()[code]
    assert again.events == scripts[code].events
    assert render(again) == golden_path(code).read_text(encoding="utf-8"), (
        f"{code} events changed; if intended, run `uv run python -m app.sim.golden`"
    )


@pytest.mark.parametrize("code", CODES)
def test_events_are_ordered_and_every_sighting_opens_and_closes(
    scripts: dict[str, Script], code: str
) -> None:
    events = scripts[code].events
    assert list(events) == sorted(events, key=ScriptEvent.sort_key)
    by_track: dict[str, list[str]] = defaultdict(list)
    for event in events:
        by_track[event.local_track_id].append(event.type)
    for types in by_track.values():
        assert types[0] == "appear" and types[-1] == "disappear"
        assert set(types[1:-1]) <= {"dwell"}


def test_a_long_stay_sends_a_dwell_every_minute(scripts: dict[str, Script]) -> None:
    script = scripts["s2-night-fence"]
    stay = [event for event in script.events if event.object_key == "t1" and event.visit == 2]
    assert [event.type for event in stay] == ["appear", "dwell", "dwell", "dwell", "disappear"]
    assert [event.ts_ms - stay[0].ts_ms for event in stay] == [0, 60_000, 120_000, 180_000, 212_000]


def test_targets_follow_their_visits(scripts: dict[str, Script]) -> None:
    script = scripts["s2-night-fence"]
    appears = [e for e in script.events if e.object_key == "t1" and e.type == "appear"]
    assert [e.node for e in appears] == [
        "s-fence-n",
        "c-back-02",
        "c-lane-2n",
        "c-main-02",
        "c-lane-2s",
        "s-fence-s",
    ]
    assert appears[1].ts_ms - appears[0].ts_ms == 4_000 + 15_500
    assert script.find(EventRef(target="t1", visit=2, type="dwell", n=3)).ts_ms == (
        appears[2].ts_ms + 180_000
    )


@pytest.mark.parametrize("code", CODES)
def test_background_moves_along_normal_routes_inside_the_link_windows(
    scripts: dict[str, Script], code: str
) -> None:
    layout = LayoutFile.model_validate_json(LAYOUT_PATH.read_text(encoding="utf-8"))
    graph = graph_from_layout(layout)
    routes = set(graph.normal_routes)
    background = [obj for obj in scripts[code].objects if not obj.is_target]
    assert len(background) == 70
    for obj in background:
        assert tuple(stop.node for stop in obj.stops) in routes
        for before, after in zip(obj.stops, obj.stops[1:], strict=False):
            edge = graph.edge(before.node, after.node)
            assert edge is not None
            low, high = edge.window(obj.object_class)
            assert low * 1000 <= after.arrive_ms - before.leave_ms <= high * 1000


@pytest.mark.parametrize("code", CODES)
def test_the_live_window_holds_the_whole_target(scripts: dict[str, Script], code: str) -> None:
    script = scripts[code]
    live = script.live_events()
    start, end = to_ms(script.window_start), to_ms(script.window_end)
    assert all(start <= event.ts_ms < end for event in live)
    target = [event for event in script.events if event.object_key == "t1"]
    assert [event for event in live if event.object_key == "t1"] == target
    # A sighting is never cut at the window's start.
    first_types = {e.local_track_id: e.type for e in reversed(live)}
    assert set(first_types.values()) == {"appear"}
