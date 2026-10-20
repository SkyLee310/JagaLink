"""M4.1: the three anomaly rules (F4), each threshold at its boundary."""

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.engine.graph import Graph, GraphNode, LinkData
from app.engine.linker import Linker, Sighting, Track
from app.engine.rules import AfterHours, Loiter, Match, OffRoute, RuleSet, evaluate

KL = ZoneInfo("Asia/Kuala_Lumpur")
# 02:00 in Kuala Lumpur (UTC+8) on the night of 21 Oct.
NIGHT = datetime(2026, 10, 21, 18, 0, tzinfo=UTC)


def graph() -> Graph:
    """Lane cameras a, b and d in zone z-lane; c on the street; a normal route a → b → c."""
    nodes = [
        GraphNode("a", "camera", 0, 0, "z-lane", "lane"),
        GraphNode("b", "camera", 100, 0, "z-lane", "lane"),
        GraphNode("c", "camera", 200, 0, "z-road", "street"),
        GraphNode("d", "camera", 100, 100, "z-lane", "lane"),
    ]
    links = [
        LinkData("a", "b", 20, 40),
        LinkData("b", "c", 20, 40),
        LinkData("b", "d", 20, 40),
        LinkData("c", "d", 20, 40),
    ]
    return Graph.build(nodes, links, [("a", "b", "c")])


class Night:
    """Feeds one object's stays to a linker, checking the rules after every event."""

    def __init__(self, rules: RuleSet | None = None) -> None:
        self.graph = graph()
        self.linker = Linker(self.graph)
        self.rules = rules or RuleSet()
        self.seen = 0
        self.matches: list[tuple[str, list[Match]]] = []

    def event(self, node: str, at_s: float, kind: str, local: str) -> list[Match]:
        self.seen += 1
        moment = NIGHT + timedelta(seconds=at_s)
        sighting = Sighting(f"e{self.seen}", moment, node, kind, "person", local)  # type: ignore[arg-type]
        track = self.linker.feed(sighting).placed
        assert isinstance(track, Track)
        found = evaluate(track, sighting, self.graph, self.rules, KL)
        self.matches.append((sighting.id, found))
        return found

    def stay(self, node: str, start_s: float, end_s: float, dwell_every: float = 0) -> None:
        local = f"{node}#{self.seen}"
        self.event(node, start_s, "appear", local)
        if dwell_every:
            moment = start_s + dwell_every
            while moment < end_s:
                self.event(node, moment, "dwell", local)
                moment += dwell_every
        self.event(node, end_s, "disappear", local)

    def rules_hit(self) -> list[tuple[str, str]]:
        return [(event_id, m.rule) for event_id, found in self.matches for m in found]


def at_local(hour: int, minute: int = 0, second: int = 0) -> float:
    """Seconds after NIGHT (02:00 local) for a local time that night."""
    moment = datetime(2026, 10, 22, hour, minute, second, tzinfo=KL)
    if hour >= 12:
        moment -= timedelta(days=1)
    return (moment - NIGHT).total_seconds()


# After-hours entry -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("local", "expected"),
    [
        ((22, 59, 59), False),
        ((23, 0, 0), True),
        ((2, 0, 0), True),
        ((5, 59, 59), True),
        ((6, 0, 0), False),
    ],
)
def test_after_hours_matches_an_appearance_in_a_lane_inside_quiet_hours(
    local: tuple[int, int, int], expected: bool
) -> None:
    night = Night()
    found = night.event("a", at_local(*local), "appear", "a#1")
    assert [m.rule for m in found] == (["after_hours"] if expected else [])
    if expected:
        assert found[0].evidence == ("e1",)
        assert found[0].node == "a"


def test_after_hours_ignores_street_zones_and_events_other_than_appear() -> None:
    night = Night()
    assert night.event("c", at_local(2), "appear", "c#1") == []
    assert night.event("c", at_local(2, 0, 5), "disappear", "c#1") == []
    night.event("a", at_local(2, 1), "appear", "a#1")
    assert night.event("a", at_local(2, 2), "dwell", "a#1") == []


def test_after_hours_reads_its_period_and_zone_kinds_from_config() -> None:
    rules = RuleSet(
        after_hours=AfterHours(start=time(1), end=time(3), zone_kinds=frozenset({"street"}))
    )
    night = Night(rules)
    assert night.event("a", at_local(2), "appear", "a#1") == []
    assert [m.rule for m in night.event("c", at_local(2, 30), "appear", "c#1")] == ["after_hours"]
    assert night.event("c", at_local(3, 0), "appear", "c#2") == []


# Loitering ---------------------------------------------------------------------------------


def loiter_only(**params: float) -> RuleSet:
    """Loitering alone: these nights run at 02:00 local, inside quiet hours."""
    off = {"after_hours": AfterHours(enabled=False), "off_route": OffRoute(enabled=False)}
    return RuleSet(loiter=Loiter(**params), **off)  # type: ignore[arg-type]


def test_loiter_fires_when_time_in_one_zone_reaches_the_threshold() -> None:
    night = Night(loiter_only())
    night.event("a", 0, "appear", "a#1")
    assert night.event("a", 179.999, "dwell", "a#1") == []
    [match] = night.event("a", 180, "dwell", "a#1")
    assert (match.rule, match.score) == ("loiter", 180.0)
    assert match.evidence == ("e1", "e2", "e3")


def test_loiter_counts_gaps_between_consecutive_stays_in_the_zone() -> None:
    night = Night(loiter_only())
    night.stay("a", 0, 10)
    night.stay("b", 40, 50)  # gap 30 s, both in z-lane: 10 + 30 + 10 = 50 s
    night.stay("d", 80, 90)  # gap 30 s: 50 + 30 + 10 = 90 s
    assert night.rules_hit() == []
    again = Night(loiter_only(threshold_s=90))
    again.stay("a", 0, 10)
    again.stay("b", 40, 50)
    again.stay("d", 80, 90)
    assert again.rules_hit() == [("e6", "loiter")]


def test_loiter_skips_gaps_through_another_zone() -> None:
    night = Night(loiter_only(threshold_s=30))
    night.stay("b", 0, 10)
    night.stay("c", 40, 50)  # the street: the b → c → d gaps do not count for z-lane
    night.stay("d", 80, 95)
    # z-lane: b 10 s + d 15 s = 25 s < 30 s.
    assert night.rules_hit() == []


def test_loiter_counts_only_time_inside_the_rolling_window() -> None:
    rules = loiter_only(threshold_s=100, window_s=120)
    night = Night(rules)
    night.stay("a", 0, 60)
    night.stay("b", 80, 100)
    # At b's disappear (100 s) the window starts at -20 s: 60 + 20 + 20 = 100 s.
    assert night.rules_hit() == [("e4", "loiter")]
    later = Night(rules)
    later.stay("a", 0, 60)
    later.stay("b", 80, 101)
    # At 101 s the window starts at -19 s; still 60 + 20 + 21 = 101 s.
    assert later.rules_hit() == [("e4", "loiter")]
    stale = Night(rules)
    stale.stay("a", 0, 30)
    stale.stay("b", 60, 150)
    # At 150 s the window starts at 30 s: a no longer counts, so 30 + 90 = 120 s; a's
    # events are not evidence.
    [(event_id, match)] = [(i, m) for i, found in stale.matches for m in found]
    assert (event_id, match.evidence) == ("e4", ("e3", "e4"))


# Off-route movement ------------------------------------------------------------------------


def test_off_route_flags_a_step_no_normal_route_takes() -> None:
    night = Night(RuleSet(after_hours=AfterHours(enabled=False)))
    night.stay("a", 0, 5)
    night.stay("b", 35, 40)  # a → b: on the normal route
    night.stay("d", 70, 75)  # b → d: no normal route takes it
    assert night.rules_hit() == [("e5", "off_route")]
    [(_, [match])] = [(i, f) for i, f in night.matches if f]
    assert match.evidence == ("e4", "e5")
    assert match.detail == "Moved b → d, a step no normal route takes."


def test_off_route_ignores_a_first_sighting_and_later_events_at_the_same_node() -> None:
    night = Night(RuleSet(after_hours=AfterHours(enabled=False), off_route=OffRoute()))
    night.stay("d", 0, 5, dwell_every=2)
    assert night.rules_hit() == []


def test_a_disabled_rule_never_matches() -> None:
    rules = RuleSet(after_hours=AfterHours(enabled=False), off_route=OffRoute(enabled=False))
    night = Night(rules)
    night.stay("b", at_local(2), at_local(2, 0, 5))
    night.stay("d", at_local(2, 0, 35), at_local(2, 0, 40))
    assert night.rules_hit() == []
