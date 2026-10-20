"""M4.4: each scenario raises exactly its expected alerts, and normal background movement stays
within the false-alert target (F4, D-68, D-72); the whole night matches the golden alert files."""

import pytest

from app.engine.alerting import AlertState
from app.engine.graph import Graph
from app.sim.golden import (
    alerts_path,
    opened_alerts,
    owners,
    render_alerts,
    roster_posts,
    script_alerts,
    script_sightings,
    seeded_graph,
    seeded_layout,
    seeded_scenarios,
    seeded_scripts,
)
from app.sim.scenario import ScenarioFile
from app.sim.script import Script

CODES = ["s1-evening-vehicle", "s2-night-fence"]
TIMEZONE = "Asia/Kuala_Lumpur"
FALSE_ALERTS_PER_CAMERA = 2  # D-68


@pytest.fixture(scope="module")
def graph() -> Graph:
    return seeded_graph()


@pytest.fixture(scope="module")
def scenarios() -> dict[str, ScenarioFile]:
    return seeded_scenarios()


@pytest.fixture(scope="module")
def scripts() -> dict[str, Script]:
    return seeded_scripts()


def test_the_seeded_layout_runs_in_kuala_lumpur_time() -> None:
    assert seeded_layout().community.timezone == TIMEZONE


@pytest.mark.parametrize("code", CODES)
def test_alerts_match_the_golden_file(
    scripts: dict[str, Script], scenarios: dict[str, ScenarioFile], graph: Graph, code: str
) -> None:
    rendered = render_alerts(scripts[code], scenarios[code], graph, TIMEZONE)
    assert rendered == alerts_path(code).read_text(encoding="utf-8"), (
        f"{code} alerts changed; if intended, run `uv run python -m app.sim.golden`"
    )


def night_alerts(
    script: Script, scenario: ScenarioFile, graph: Graph
) -> list[tuple[str, AlertState]]:
    """Every alert of the whole night, with the one true object behind its evidence."""
    owner = owners(script)
    changes = script_alerts(script.events, graph, roster_posts(scenario), TIMEZONE)
    found = []
    for _, final, _ in opened_alerts(changes):
        [obj] = {owner[event_id] for event_id in final.evidence}
        found.append((obj, final))
    return found


@pytest.mark.parametrize("code", CODES)
def test_each_target_raises_exactly_its_expected_alerts(
    scripts: dict[str, Script], scenarios: dict[str, ScenarioFile], graph: Graph, code: str
) -> None:
    script, scenario = scripts[code], scenarios[code]
    targets = {obj.key for obj in script.objects if obj.is_target}
    raised = sorted(
        (obj, alert.rule) for obj, alert in night_alerts(script, scenario, graph) if obj in targets
    )
    expected = sorted((alert.target, alert.rule) for alert in scenario.truth.expected_alerts)
    assert raised == expected


@pytest.mark.parametrize("code", CODES)
def test_background_movement_stays_within_the_false_alert_target(
    scripts: dict[str, Script], scenarios: dict[str, ScenarioFile], graph: Graph, code: str
) -> None:
    script = scripts[code]
    targets = {obj.key for obj in script.objects if obj.is_target}
    background = [
        alert for obj, alert in night_alerts(script, scenarios[code], graph) if obj not in targets
    ]
    cameras = sum(1 for node in graph.nodes.values() if node.kind == "camera")
    assert len(background) / cameras <= FALSE_ALERTS_PER_CAMERA


@pytest.mark.parametrize("code", CODES)
def test_the_live_window_raises_only_the_targets_alerts(
    scripts: dict[str, Script], scenarios: dict[str, ScenarioFile], graph: Graph, code: str
) -> None:
    """What the demo plays (D-71): the target's alerts, and nothing from the background."""
    script, scenario = scripts[code], scenarios[code]
    events = script.live_events()
    owner = {s.id: e.object_key for s, e in zip(script_sightings(events), events, strict=True)}
    changes = script_alerts(events, graph, roster_posts(scenario), TIMEZONE)
    raised = sorted(
        ({owner[event_id] for event_id in final.evidence}.pop(), final.rule)
        for _, final, _ in opened_alerts(changes)
    )
    assert raised == sorted((alert.target, alert.rule) for alert in scenario.truth.expected_alerts)
