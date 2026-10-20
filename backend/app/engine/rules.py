"""Anomaly rules (F4): three human-defined rules over one anonymous track (D-18, D-52–D-54).

Pure: a track and the sighting that just joined it go in, matches come out, with no database,
network or wall clock (D-32). Thresholds arrive in a `RuleSet` that the database's `rule_config`
fills, so changing one needs no code (F4). Rules read the community's local time (D-54) and look
only at where and when an object was seen, never at who it is (D-09).
"""

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from app.engine.graph import Graph
from app.engine.linker import Segment, Sighting, Track

RuleKey = Literal["after_hours", "loiter", "off_route"]
RULE_KEYS: tuple[RuleKey, ...] = ("after_hours", "loiter", "off_route")
Severity = Literal["high", "medium", "low"]
ZoneKind = Literal["street", "gate", "lane"]

RULE_NAMES: dict[RuleKey, str] = {
    "after_hours": "After-hours entry",
    "loiter": "Loitering",
    "off_route": "Off-route movement",
}


@dataclass(frozen=True)
class AfterHours:
    """An appearance in one of `zone_kinds` during the quiet period, which may span midnight."""

    enabled: bool = True
    start: time = time(23, 0)
    end: time = time(6, 0)
    zone_kinds: frozenset[ZoneKind] = frozenset({"lane"})
    severity: Severity = "medium"

    def quiet(self, moment: time) -> bool:
        if self.start <= self.end:
            return self.start <= moment < self.end
        return moment >= self.start or moment < self.end


@dataclass(frozen=True)
class Loiter:
    """At least `threshold_s` in one zone within the last `window_s` (D-52)."""

    enabled: bool = True
    threshold_s: float = 180.0
    window_s: float = 600.0
    severity: Severity = "medium"


@dataclass(frozen=True)
class OffRoute:
    """A step between two nodes that no normal route takes (D-53)."""

    enabled: bool = True
    severity: Severity = "high"


@dataclass(frozen=True)
class RuleSet:
    after_hours: AfterHours = field(default_factory=AfterHours)
    loiter: Loiter = field(default_factory=Loiter)
    off_route: OffRoute = field(default_factory=OffRoute)

    def severity(self, rule: RuleKey) -> Severity:
        """The rule's own severity (D-60), before two rules on one track raise it."""
        return getattr(self, rule).severity


@dataclass(frozen=True)
class Match:
    """One rule matching one sighting, with the events it relied on (D-18)."""

    rule: RuleKey
    ts: datetime
    node: str
    evidence: tuple[str, ...]
    detail: str
    """Why it matched, in words for the alert card."""
    score: float | None = None
    """Loitering: the seconds counted in the zone."""


def evaluate(
    track: Track, sighting: Sighting, graph: Graph, rules: RuleSet, zone: ZoneInfo
) -> list[Match]:
    """Every rule the sighting makes the track match, in `RULE_KEYS` order. The sighting must
    be the latest one the linker placed in this track."""
    found = []
    if rules.after_hours.enabled:
        found.append(after_hours(sighting, graph, rules.after_hours, zone))
    if rules.loiter.enabled:
        found.append(loiter(track, sighting, graph, rules.loiter))
    if rules.off_route.enabled:
        found.append(off_route(track, sighting, graph))
    return [match for match in found if match is not None]


def after_hours(
    sighting: Sighting, graph: Graph, params: AfterHours, zone: ZoneInfo
) -> Match | None:
    node = graph.nodes.get(sighting.node)
    if sighting.type != "appear" or node is None or node.zone_kind not in params.zone_kinds:
        return None
    local = sighting.ts.astimezone(zone)
    if not params.quiet(local.time()):
        return None
    quiet = f"{params.start:%H:%M}–{params.end:%H:%M}"
    detail = (
        f"Appeared at {sighting.node}, in a {node.zone_kind} zone, at {local:%H:%M}: "
        f"inside quiet hours {quiet}."
    )
    return Match("after_hours", sighting.ts, sighting.node, (sighting.id,), detail)


def loiter(track: Track, sighting: Sighting, graph: Graph, params: Loiter) -> Match | None:
    """Time in the sighting's zone within the window: each stay there, and each gap between
    two consecutive stays that are both there (D-52), so repeat passes add up."""
    node = graph.nodes.get(sighting.node)
    if node is None or node.zone is None:
        return None
    now = sighting.ts
    since = now - timedelta(seconds=params.window_s)
    total = 0.0
    evidence: list[str] = []
    for start, end, segment in _zone_spans(track.segments, graph, node.zone, now):
        total += max((min(end, now) - max(start, since)).total_seconds(), 0.0)
        # A stay that reaches into the window is evidence, even one that has just begun.
        if segment is not None and end > since:
            evidence += segment.event_ids
    if total < params.threshold_s:
        return None
    detail = (
        f"{total:.0f} s in zone {node.zone} within {params.window_s / 60:g} min "
        f"(threshold {params.threshold_s:g} s)."
    )
    return Match("loiter", now, sighting.node, tuple(evidence), detail, round(total, 3))


def _zone_spans(
    segments: list[Segment], graph: Graph, zone: str, now: datetime
) -> Iterator[tuple[datetime, datetime, Segment | None]]:
    """Each stay in the zone, and each gap between consecutive stays in it (segment None)."""
    previous: Segment | None = None
    for segment in segments:
        node = graph.nodes.get(segment.node)
        inside = node is not None and node.zone == zone
        if inside:
            if previous is not None and previous.exit is not None:
                yield previous.exit, segment.enter, None
            yield segment.enter, segment.exit or now, segment
        previous = segment if inside else None


def off_route(track: Track, sighting: Sighting, graph: Graph) -> Match | None:
    """Only the appear that moved the track to a new node is a step."""
    if sighting.type != "appear" or len(track.segments) < 2:
        return None
    before, head = track.segments[-2], track.head
    if head.event_ids[:1] != [sighting.id]:
        return None
    if (before.node, head.node) in graph.normal_transitions():
        return None
    detail = f"Moved {before.node} → {head.node}, a step no normal route takes."
    evidence = (*before.event_ids[-1:], sighting.id)
    return Match("off_route", sighting.ts, head.node, evidence, detail)
