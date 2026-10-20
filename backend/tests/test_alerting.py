"""M4.4: rule matches become alerts: one per (track, rule), rule-based severity, routing."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app.engine.alerting import AlertChange, Alerter
from app.engine.graph import Graph, GraphNode, LinkData
from app.engine.linker import Linker, Sighting
from app.engine.router import GuardPost
from app.engine.rules import AfterHours, Loiter, RuleSet

KL = ZoneInfo("Asia/Kuala_Lumpur")
TWO_AM = datetime(2026, 10, 21, 18, 0, tzinfo=UTC)  # 02:00 in Kuala Lumpur


def graph() -> Graph:
    """Lane cameras a, b and c in a row; the only normal route is a → b."""
    nodes = [
        GraphNode("a", "camera", 0, 0, "z-lane", "lane"),
        GraphNode("b", "camera", 100, 0, "z-lane", "lane"),
        GraphNode("c", "camera", 200, 0, "z-lane", "lane"),
    ]
    links = [LinkData("a", "b", 20, 40), LinkData("b", "c", 20, 40)]
    return Graph.build(nodes, links, [("a", "b")])


class Run:
    def __init__(self, rules: RuleSet, guards: list[GuardPost]) -> None:
        self.linker = Linker(graph())
        self.alerter = Alerter(graph(), rules, guards, KL)
        self.count = 0

    def stay(self, node: str, start_s: float, end_s: float) -> list[AlertChange]:
        changes: list[AlertChange] = []
        local = f"{node}#{self.count}"
        for at_s, kind in ((start_s, "appear"), (end_s, "disappear")):
            self.count += 1
            moment = TWO_AM + timedelta(seconds=at_s)
            sighting = Sighting(f"e{self.count}", moment, node, kind, "person", local)  # type: ignore[arg-type]
            placed = self.linker.feed(sighting).placed
            assert placed is not None
            changes += self.alerter.observe(placed, sighting)
        return changes


GUARDS = [GuardPost("u-guard-01", "c", on_duty=True), GuardPost("u-guard-02", "a", on_duty=True)]


def summary(changes: list[AlertChange]) -> list[tuple[str, str, str, list[str]]]:
    return [(c.kind, c.alert.rule, c.alert.severity, c.alert.evidence) for c in changes]


def test_a_repeat_match_adds_evidence_to_the_open_alert() -> None:
    run = Run(RuleSet(), GUARDS)
    first = run.stay("a", 0, 5)
    assert summary(first) == [("alert", "after_hours", "medium", ["e1"])]
    assert first[0].alert.guard == "u-guard-02"  # already at a
    assert first[0].alert.severity_reason == "Rule-based: after-hours entry is rated medium."
    assert first[0].alert.next_camera is not None and first[0].alert.next_camera.node == "b"

    # a → b is a normal step; the after-hours alert gains b's appear and moves to b.
    second = run.stay("b", 35, 40)
    assert summary(second) == [("alert_update", "after_hours", "medium", ["e1", "e3"])]
    assert second[0].alert.node == "b"
    assert second[0].alert.first_ts == TWO_AM
    assert second[0].alert.last_ts == second[0].alert.updated_ts == TWO_AM + timedelta(seconds=35)


def test_a_second_rule_on_one_track_raises_every_alert_on_it_to_high() -> None:
    run = Run(RuleSet(), GUARDS)
    run.stay("a", 0, 5)
    run.stay("b", 35, 40)
    # b → c is off-route: a new high alert, and the after-hours alert goes to high too (D-60).
    changes = run.stay("c", 70, 75)
    assert [(c.kind, c.alert.rule, c.alert.severity) for c in changes] == [
        ("alert", "off_route", "high"),
        ("alert_update", "after_hours", "high"),
    ]
    reason = "Rule-based: 2 rules matched this path (after-hours entry, off-route movement)."
    assert {c.alert.severity_reason for c in changes} == {reason}
    assert {c.alert.updated_ts for c in changes} == {TWO_AM + timedelta(seconds=70)}
    assert changes[0].alert.guard == "u-guard-01"
    assert changes[0].alert.walk_s == 0.0


def test_with_nobody_on_duty_the_alert_escalates() -> None:
    run = Run(RuleSet(), [GuardPost("u-guard-01", "c", on_duty=False)])
    [change] = run.stay("a", 0, 5)
    assert (change.alert.guard, change.alert.walk_s) == (None, None)


def test_changes_are_snapshots_and_an_expired_track_is_forgotten() -> None:
    rules = RuleSet(after_hours=AfterHours(enabled=False), loiter=Loiter(threshold_s=10))
    run = Run(rules, GUARDS)
    [opened] = run.stay("a", 0, 20)[:1]
    assert opened.alert.evidence == ["e1", "e2"]
    later = run.stay("b", 45, 50)  # 25 s after leaving a: the same track
    assert later[-1].alert.evidence == ["e1", "e2", "e3", "e4"]
    assert opened.alert.evidence == ["e1", "e2"]
    run.alerter.forget(1)
    assert run.alerter.alerts == {}
