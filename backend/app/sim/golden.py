"""Golden event files: each scenario's whole night, one event per line, checked by `make test`.

    uv run python -m app.sim.golden     rewrite every golden file from the current code

Rewrite them only for an intended change in the events, and say so in the commit (AGENTS.md).
"""

import json
from pathlib import Path

from app.schemas.layout import LayoutFile
from app.sim.scenario import SCENARIO_DIR, graph_from_layout, load_scenario, scenario_paths
from app.sim.script import Script, ScriptEvent, build_script

GOLDEN_DIR = SCENARIO_DIR / "golden"
LAYOUT_PATH = SCENARIO_DIR.parent / "layouts" / "taman-simulasi.json"


def event_line(event: ScriptEvent) -> str:
    """The posted fields, then the object it belongs to (ground truth, never posted)."""
    ts = event.ts.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    fields = [ts, event.node, event.type, event.object_class, event.local_track_id]
    return json.dumps([*fields, event.object_key], separators=(",", ":"))


def golden_path(code: str) -> Path:
    return GOLDEN_DIR / f"{code}.events.jsonl"


def seeded_scripts() -> dict[str, Script]:
    """Every scenario's script on the seeded layout, by scenario code."""
    layout = LayoutFile.model_validate_json(LAYOUT_PATH.read_text(encoding="utf-8"))
    graph = graph_from_layout(layout)
    scripts = {}
    for path in scenario_paths():
        scenario = load_scenario(path)
        scripts[scenario.code] = build_script(scenario, graph, layout.community.timezone)
    return scripts


def render(script: Script) -> str:
    return "".join(event_line(event) + "\n" for event in script.events)


def main() -> None:
    GOLDEN_DIR.mkdir(exist_ok=True)
    for code, script in seeded_scripts().items():
        path = golden_path(code)
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(render(script))
        print(f"wrote {path.name}: {len(script.events)} events")


if __name__ == "__main__":
    main()
