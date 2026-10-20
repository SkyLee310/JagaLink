"""M2.1: scenario files load, fit the seeded layout, and refuse what cannot run."""

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from app.schemas.layout import LayoutFile
from app.sim.golden import LAYOUT_PATH
from app.sim.scenario import (
    NightClock,
    ScenarioFile,
    check_scenario,
    graph_from_layout,
    load_scenario,
    scenario_paths,
)

USERS = ["u-sup-01", "u-guard-01", "u-guard-02", "u-guard-03"]


@pytest.fixture(scope="module")
def layout() -> LayoutFile:
    return LayoutFile.model_validate_json(LAYOUT_PATH.read_text(encoding="utf-8"))


def scenario(code: str) -> ScenarioFile:
    return next(load_scenario(path) for path in scenario_paths() if path.stem == code)


def test_both_scenarios_load_and_fit_the_seeded_layout(layout: LayoutFile) -> None:
    graph = graph_from_layout(layout)
    paths = scenario_paths()
    assert [path.stem for path in paths] == ["s1-evening-vehicle", "s2-night-fence"]
    for path in paths:
        loaded = load_scenario(path)
        assert loaded.code == path.stem
        assert loaded.community == layout.community.slug
        assert check_scenario(loaded, graph, USERS) == []


def test_the_scenarios_match_d15() -> None:
    s1, s2 = scenario("s1-evening-vehicle"), scenario("s2-night-fence")
    assert [target.object_class for target in s1.targets] == ["vehicle"]
    assert s1.targets[0].visits[0].at == "19:20:00"
    assert [target.object_class for target in s2.targets] == ["person"]
    assert s2.targets[0].visits[0].at == "02:10:00"


def test_local_times_become_utc_and_the_small_hours_fall_on_the_next_day() -> None:
    clock = NightClock(scenario("s2-night-fence").night, "Asia/Kuala_Lumpur")
    assert clock.start == datetime(2026, 10, 21, 10, 0, tzinfo=UTC)
    assert clock.at("19:20:00") == datetime(2026, 10, 21, 11, 20, tzinfo=UTC)
    assert clock.at("02:10:30.5") == datetime(2026, 10, 21, 18, 10, 30, 500000, tzinfo=UTC)
    assert clock.end == datetime(2026, 10, 21, 22, 0, tzinfo=UTC)
    assert clock.local(clock.at("02:10")).date() == date(2026, 10, 22)


def broken(**changes: object) -> ScenarioFile:
    data = scenario("s2-night-fence").model_dump(mode="json")
    visits = data["targets"][0]["visits"]
    for key, value in changes.items():
        if key == "visit2":
            visits[2].update(value)
        elif key == "roster":
            data["roster"] = value
        elif key == "first_unusual":
            data["truth"]["first_unusual"] = value
        elif key == "window":
            data["live_window"] = value
    return ScenarioFile.model_validate(data)


@pytest.mark.parametrize(
    ("changes", "problem"),
    [
        ({"visit2": {"node": "c-lane-9n"}}, "t1 visit 2 names unknown node c-lane-9n"),
        ({"visit2": {"node": "c-lane-3n"}}, "t1 visit 2: no link c-back-02 -> c-lane-3n"),
        (
            {"visit2": {"after_s": 12}},
            "t1 visit 2: 12.0 s from c-back-02 is outside the person window 28-34 s",
        ),
        (
            {"roster": [{"user": "u-guard-09", "on_duty": True, "node": "c-gate-01"}]},
            "roster names unknown user u-guard-09",
        ),
        (
            {"first_unusual": {"target": "t1", "visit": 9, "type": "appear"}},
            "truth names visit 9 of t1, which has fewer",
        ),
        (
            {"window": {"start": "05:00", "end": "07:00"}},
            "the live window must lie inside the night, start before it ends",
        ),
    ],
)
def test_check_refuses_what_cannot_run(
    layout: LayoutFile, changes: dict[str, object], problem: str
) -> None:
    graph = graph_from_layout(layout)
    assert problem in check_scenario(broken(**changes), graph, USERS)


def test_an_unlinked_normal_route_is_refused(layout: LayoutFile) -> None:
    data = layout.model_dump(mode="json")
    data["links"] = [
        link
        for link in data["links"]
        if {link["from_node"], link["to_node"]} != {"c-main-01", "c-lane-1n"}
    ]
    graph = graph_from_layout(LayoutFile.model_validate(data))
    problems = check_scenario(scenario("s1-evening-vehicle"), graph, USERS)
    assert "normal route 1: no link c-main-01 -> c-lane-1n" in problems


def test_visit_timing_must_be_given_one_way() -> None:
    data = scenario("s2-night-fence").model_dump(mode="json")
    data["targets"][0]["visits"][1]["at"] = "02:11"
    with pytest.raises(ValidationError, match="every later visit needs `after_s` and no `at`"):
        ScenarioFile.model_validate(data)
