"""Golden files: each scenario's whole night, checked by `make test`.

    uv run python -m app.sim.golden     rewrite every golden file from the current code

`<code>.events.jsonl` holds one event per line (F2); `<code>.paths.jsonl` holds one linked track
per line (F3). Rewrite them only for an intended change, and say so in the commit (AGENTS.md).
"""

import json
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from app.engine.graph import Graph
from app.engine.linker import Sighting, Track, link_all
from app.schemas.layout import LayoutFile
from app.sim.scenario import SCENARIO_DIR, graph_from_layout, load_scenario, scenario_paths
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


def seeded_layout() -> LayoutFile:
    return LayoutFile.model_validate_json(LAYOUT_PATH.read_text(encoding="utf-8"))


def seeded_graph() -> Graph:
    return graph_from_layout(seeded_layout())


def seeded_scripts() -> dict[str, Script]:
    """Every scenario's script on the seeded layout, by scenario code."""
    layout = seeded_layout()
    graph = graph_from_layout(layout)
    scripts = {}
    for path in scenario_paths():
        scenario = load_scenario(path)
        scripts[scenario.code] = build_script(scenario, graph, layout.community.timezone)
    return scripts


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


def main() -> None:
    GOLDEN_DIR.mkdir(exist_ok=True)
    graph = seeded_graph()
    for code, script in seeded_scripts().items():
        for path, text, what in (
            (golden_path(code), render(script), f"{len(script.events)} events"),
            (paths_path(code), render_paths(script, graph), "paths"),
        ):
            with path.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
            print(f"wrote {path.name}: {what}")


if __name__ == "__main__":
    main()
