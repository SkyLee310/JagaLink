"""Golden files: each scenario's whole night, checked by `make test`.

    uv run python -m app.sim.golden     rewrite every golden file from the current code

`<code>.events.jsonl` holds one event per line (F2); `<code>.paths.jsonl` holds one linked track
per line (F3); `<code>.alerts.jsonl` holds one alert per line (F4, F5). Rewrite them only for an
intended change, and say so in the commit (AGENTS.md).
"""

import json
from collections import Counter
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.engine.alerting import AlertChange, Alerter, AlertState, link_and_check
from app.engine.graph import Graph
from app.engine.linker import Linker, Sighting, Track, link_all
from app.engine.router import GuardPost
from app.engine.rules import RuleKey, RuleSet
from app.schemas.layout import LayoutFile
from app.sim.scenario import (
    SCENARIO_DIR,
    ScenarioFile,
    graph_from_layout,
    load_scenario,
    scenario_paths,
)
from app.sim.script import Script, ScriptEvent, build_script

GOLDEN_DIR = SCENARIO_DIR / "golden"
LAYOUT_PATH = SCENARIO_DIR.parent / "layouts" / "taman-simulasi.json"


def iso(moment: datetime) -> str:
    return moment.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def event_line(event: ScriptEvent) -> str:
    """The posted fields, then the object it belongs to (ground truth, never posted)."""
    fields = [iso(event.ts), event.node, event.type, event.object_class, event.local_track_id]
    return json.dumps([*fields, event.object_key], separators=(",", ":"))


def golden_path(code: str) -> Path:
    return GOLDEN_DIR / f"{code}.events.jsonl"


def paths_path(code: str) -> Path:
    return GOLDEN_DIR / f"{code}.paths.jsonl"


def alerts_path(code: str) -> Path:
    return GOLDEN_DIR / f"{code}.alerts.jsonl"


def seeded_layout() -> LayoutFile:
    return LayoutFile.model_validate_json(LAYOUT_PATH.read_text(encoding="utf-8"))


def seeded_graph() -> Graph:
    return graph_from_layout(seeded_layout())


def seeded_scenarios() -> dict[str, ScenarioFile]:
    """Every scenario file, by scenario code."""
    return {scenario.code: scenario for scenario in map(load_scenario, scenario_paths())}


def seeded_scripts() -> dict[str, Script]:
    """Every scenario's script on the seeded layout, by scenario code."""
    layout = seeded_layout()
    graph = graph_from_layout(layout)
    timezone = layout.community.timezone
    return {
        code: build_script(scenario, graph, timezone)
        for code, scenario in seeded_scenarios().items()
    }


def render(script: Script) -> str:
    return "".join(event_line(event) + "\n" for event in script.events)


def script_sightings(events: Sequence[ScriptEvent]) -> list[Sighting]:
    """The events as the linker reads them; an event's ID is its posting order, from 1."""
    return [
        Sighting(str(number), e.ts, e.node, e.type, e.object_class, e.local_track_id)
        for number, e in enumerate(events, start=1)
    ]


def script_tracks(script: Script, graph: Graph) -> list[Track]:
    """The whole night linked as the pipeline would link it (D-35)."""
    return link_all(graph, script_sightings(script.events))


def owners(script: Script) -> dict[str, str]:
    """Each event ID's true object (ground truth, D-70)."""
    return {str(number): e.object_key for number, e in enumerate(script.events, start=1)}


def path_line(track: Track, owner: dict[str, str]) -> str:
    """A track's number, class, status and stays, then the true objects behind its events."""
    stays = [
        [segment.node, iso(segment.enter), iso(segment.exit) if segment.exit else None]
        for segment in track.segments
    ]
    objects = sorted({owner[event_id] for event_id in track.event_ids()})
    fields = [track.number, track.object_class, track.status, stays, objects]
    return json.dumps(fields, separators=(",", ":"))


def render_paths(script: Script, graph: Graph) -> str:
    owner = owners(script)
    return "".join(path_line(track, owner) + "\n" for track in script_tracks(script, graph))


def roster_posts(scenario: ScenarioFile) -> list[GuardPost]:
    """Where the scenario's roster puts each guard for the run (D-58)."""
    return [GuardPost(entry.user, entry.node, entry.on_duty) for entry in scenario.roster]


def script_alerts(
    events: Sequence[ScriptEvent], graph: Graph, guards: Sequence[GuardPost], timezone: str
) -> list[AlertChange]:
    """Every alert change the events raise, in order, as the pipeline makes them on the seeded
    rules (D-35); event IDs are posting order, as in `script_sightings`."""
    linker = Linker(graph)
    alerter = Alerter(graph, RuleSet(), guards, ZoneInfo(timezone))
    found: list[AlertChange] = []
    for sighting in script_sightings(events):
        found += link_and_check(linker, alerter, sighting)[1]
    return found


def opened_alerts(changes: Sequence[AlertChange]) -> list[tuple[AlertState, AlertState, int]]:
    """Each alert in the order it opened: as it opened, as it ended, and how many updates."""
    first: dict[tuple[int, RuleKey], AlertState] = {}
    last: dict[tuple[int, RuleKey], AlertState] = {}
    updates: Counter[tuple[int, RuleKey]] = Counter()
    for change in changes:
        key = (change.alert.track, change.alert.rule)
        if change.kind == "alert":
            first[key] = change.alert
        else:
            updates[key] += 1
        last[key] = change.alert
    return [(state, last[key], updates[key]) for key, state in first.items()]


def alert_line(opened: AlertState, final: AlertState, updates: int, owner: dict[str, str]) -> str:
    """What the guard first sees (track, rule, time, node, severity, guard, walk, next camera),
    then how it ended (updates, severity, last change, evidence count) and the true objects
    behind its evidence."""
    nearest = opened.next_camera.node if opened.next_camera else None
    first = [opened.track, opened.rule, iso(opened.first_ts), opened.node, opened.severity]
    first += [opened.guard, opened.walk_s, nearest]
    end = [updates, final.severity, iso(final.updated_ts), len(final.evidence)]
    objects = sorted({owner[event_id] for event_id in final.evidence})
    return json.dumps([*first, *end, objects], separators=(",", ":"))


def render_alerts(script: Script, scenario: ScenarioFile, graph: Graph, timezone: str) -> str:
    changes = script_alerts(script.events, graph, roster_posts(scenario), timezone)
    owner = owners(script)
    return "".join(
        alert_line(opened, final, updates, owner) + "\n"
        for opened, final, updates in opened_alerts(changes)
    )


def main() -> None:
    GOLDEN_DIR.mkdir(exist_ok=True)
    layout = seeded_layout()
    graph = graph_from_layout(layout)
    scenarios = seeded_scenarios()
    for code, script in seeded_scripts().items():
        alerts = render_alerts(script, scenarios[code], graph, layout.community.timezone)
        for path, text, what in (
            (golden_path(code), render(script), f"{len(script.events)} events"),
            (paths_path(code), render_paths(script, graph), "paths"),
            (alerts_path(code), alerts, "alerts"),
        ):
            with path.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
            print(f"wrote {path.name}: {what}")


if __name__ == "__main__":
    main()
