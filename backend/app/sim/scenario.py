"""Scenario files (F2): the scripted targets, the background traffic and the ground truth.

A file lives in `backend/data/scenarios/` and references nodes and users by code (D-75). Times are
local to the community (D-54): a night starts on `night.date`, and any time before noon belongs to
the next morning. The ground truth (`truth`, the target labels) stays in the file: the player
never posts it, so the pipeline cannot see it (D-70).
"""

from collections.abc import Sequence
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Annotated, Literal, Self
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.engine.events import EventType, ObjectClass
from app.engine.graph import Graph, GraphNode, LinkData
from app.schemas.common import Code
from app.schemas.layout import LayoutFile

SCENARIO_DIR = Path(__file__).resolve().parents[2] / "data" / "scenarios"

LocalTime = Annotated[
    str, StringConstraints(pattern=r"^([01]\d|2[0-3]):[0-5]\d(:[0-5]\d(\.\d{1,3})?)?$")
]
Rule = Literal["after_hours", "loiter", "off_route"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Night(Strict):
    date: date
    """The evening the night starts on."""
    start: LocalTime = "18:00"
    end: LocalTime = "06:00"


class Window(Strict):
    start: LocalTime
    end: LocalTime


class RosterEntry(Strict):
    """Where a guard stands during the run (D-58)."""

    user: Code
    on_duty: bool
    node: Code | None = None


class Visit(Strict):
    """One stop in front of a camera or sensor."""

    node: Code
    at: LocalTime | None = None
    """Arrival, for the first visit only."""
    after_s: float | None = Field(default=None, gt=0)
    """Travel time from the previous visit's departure, for every later visit."""
    stay_s: float = Field(gt=0, le=3600)


class Target(Strict):
    """A scripted object whose path is the ground truth."""

    key: Code
    label: str
    object_class: ObjectClass
    visits: list[Visit] = Field(min_length=1)

    @model_validator(mode="after")
    def check_timing(self) -> Self:
        first, *rest = self.visits
        if first.at is None or first.after_s is not None:
            raise ValueError(f"{self.key}: the first visit needs `at` and no `after_s`")
        if any(visit.at is not None or visit.after_s is None for visit in rest):
            raise ValueError(f"{self.key}: every later visit needs `after_s` and no `at`")
        return self


class Background(Strict):
    """Seeded normal movement along the community's normal routes (D-71)."""

    seed: int
    trips_per_hour: dict[Annotated[str, StringConstraints(pattern=r"^([01]\d|2[0-3])$")], int]
    vehicle_share: float = Field(ge=0, le=1)


class EventRef(Strict):
    """One target event: a visit's appear or disappear, or its n-th dwell (from 1)."""

    target: Code
    visit: int = Field(ge=0)
    type: EventType = "appear"
    n: int | None = Field(default=None, ge=1)


class ExpectedAlert(Strict):
    target: Code
    rule: Rule


class ExpectedEntry(Strict):
    text: str
    events: list[EventRef] = Field(min_length=1)


class Truth(Strict):
    first_unusual: EventRef
    expected_alerts: list[ExpectedAlert]
    expected_timeline: list[ExpectedEntry]


class ScenarioFile(Strict):
    code: Code
    name: str
    description: str
    community: Code
    night: Night
    live_window: Window
    default_speed: float = Field(gt=0, le=120)
    roster: list[RosterEntry]
    targets: list[Target] = Field(min_length=1)
    background: Background
    truth: Truth


def load_scenario(path: Path) -> ScenarioFile:
    return ScenarioFile.model_validate_json(path.read_text(encoding="utf-8"))


def scenario_paths(directory: Path = SCENARIO_DIR) -> list[Path]:
    return sorted(directory.glob("*.json"))


def _clock_time(text: str) -> time:
    hours, minutes, *rest = text.split(":")
    seconds = float(rest[0]) if rest else 0.0
    whole = int(seconds)
    return time(int(hours), int(minutes), whole, round((seconds - whole) * 1_000_000))


class NightClock:
    """Turns a scenario's local times into UTC instants (D-54)."""

    def __init__(self, night: Night, timezone: str) -> None:
        self.night = night
        self.zone = ZoneInfo(timezone)
        self.start = self.at(night.start)
        self.end = self.at(night.end)

    def at(self, local: str) -> datetime:
        """The UTC instant of a local time; hours before noon fall on the next morning."""
        moment = _clock_time(local)
        day = self.night.date + timedelta(days=1 if moment.hour < 12 else 0)
        return datetime.combine(day, moment, tzinfo=self.zone).astimezone(ZoneInfo("UTC"))

    def hour_start(self, hour: int) -> datetime:
        return self.at(f"{hour:02d}:00")

    def local(self, moment: datetime) -> datetime:
        return moment.astimezone(self.zone)


def graph_from_layout(layout: LayoutFile) -> Graph:
    """The engine's graph for a layout file (the seed or an export)."""
    zone_kinds = {zone.code: zone.kind for zone in layout.zones}
    return Graph.build(
        [
            GraphNode(
                code=node.code,
                kind=node.kind,
                x=node.x,
                y=node.y,
                zone=node.zone,
                zone_kind=zone_kinds.get(node.zone) if node.zone else None,
                online=node.status == "online",
            )
            for node in layout.nodes
        ],
        [
            LinkData(
                link.from_node,
                link.to_node,
                link.travel_min_s,
                link.travel_max_s,
                link.bidirectional,
                link.distance_m,
            )
            for link in layout.links
        ],
        [route.nodes for route in layout.normal_routes],
    )


def check_scenario(scenario: ScenarioFile, graph: Graph, user_codes: Sequence[str]) -> list[str]:
    """Every way the scenario does not fit this layout and staff; an empty list means it runs.

    A layout edited after the scenario was written can break it, so runs check this first.
    """
    problems: list[str] = []
    clock = NightClock(scenario.night, "UTC")

    def known(code: str, where: str) -> bool:
        if code in graph.nodes:
            return True
        problems.append(f"{where} names unknown node {code}")
        return False

    for entry in scenario.roster:
        if entry.user not in user_codes:
            problems.append(f"roster names unknown user {entry.user}")
        if entry.node is not None:
            known(entry.node, f"roster entry {entry.user}")
        if entry.on_duty and entry.node is None:
            problems.append(f"roster entry {entry.user} is on duty but has no node")

    window_start = clock.at(scenario.live_window.start)
    window_end = clock.at(scenario.live_window.end)
    if not clock.start <= window_start < window_end <= clock.end:
        problems.append("the live window must lie inside the night, start before it ends")

    keys = [target.key for target in scenario.targets]
    for key in {key for key in keys if keys.count(key) > 1}:
        problems.append(f"target key {key} is used twice")
    for target in scenario.targets:
        for index, visit in enumerate(target.visits):
            if not known(visit.node, f"{target.key} visit {index}"):
                continue
            if index == 0 or visit.after_s is None:
                continue
            previous = target.visits[index - 1].node
            edge = graph.edge(previous, visit.node)
            if edge is None:
                if previous in graph.nodes:
                    link = f"{previous} -> {visit.node}"
                    problems.append(f"{target.key} visit {index}: no link {link}")
                continue
            low, high = edge.window(target.object_class)
            if not low <= visit.after_s <= high:
                problems.append(
                    f"{target.key} visit {index}: {visit.after_s} s from {previous} is outside "
                    f"the {target.object_class} window {low:g}-{high:g} s"
                )

    for number, route in enumerate(graph.normal_routes, start=1):
        for start, end in zip(route, route[1:], strict=False):
            if graph.edge(start, end) is None:
                problems.append(f"normal route {number}: no link {start} -> {end}")

    targets = {target.key: target for target in scenario.targets}
    refs = [scenario.truth.first_unusual]
    refs += [ref for entry in scenario.truth.expected_timeline for ref in entry.events]
    for ref in refs:
        target = targets.get(ref.target)
        if target is None:
            problems.append(f"truth names unknown target {ref.target}")
        elif ref.visit >= len(target.visits):
            problems.append(f"truth names visit {ref.visit} of {ref.target}, which has fewer")
        elif ref.type == "dwell" and (
            ref.n is None or ref.n * 60 >= target.visits[ref.visit].stay_s
        ):
            problems.append(f"truth names a dwell that {ref.target} visit {ref.visit} never sends")
    problems += [
        f"truth expects an alert for unknown target {alert.target}"
        for alert in scenario.truth.expected_alerts
        if alert.target not in targets
    ]
    return problems
