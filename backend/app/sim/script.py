"""Turn a scenario into its ordered event list (F2), with the ground truth kept beside each event.

Pure and deterministic: the same file and layout give the same events on every run (D-27), and
background trips come from a generator seeded by the file (D-71). Each event carries its object
and visit for the evaluation; the player posts only the event contract (D-16, D-70).
"""

import random
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Literal

from app.engine.graph import Graph, ObjectClass
from app.sim.scenario import EventRef, NightClock, ScenarioFile, Target

EventType = Literal["appear", "dwell", "disappear"]

EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
TYPE_RANK: dict[str, int] = {"appear": 0, "dwell": 1, "disappear": 2}
DWELL_EVERY_MS = 60_000
"""While an object stays in view, its camera repeats a `dwell` event every minute."""

# Background objects pass a camera quickly, and a vehicle drives at about 2-3 times walking
# speed: 0.32-0.45 of the walking minimum keeps it inside the vehicle window (D-55).
STAY_S: dict[ObjectClass, tuple[float, float]] = {"person": (3.0, 8.0), "vehicle": (2.0, 5.0)}
VEHICLE_TRAVEL_SHARE = (0.32, 0.45)


def to_ms(moment: datetime) -> int:
    return (moment - EPOCH) // timedelta(milliseconds=1)


def from_ms(ms: int) -> datetime:
    return EPOCH + timedelta(milliseconds=ms)


@dataclass(frozen=True)
class Stop:
    node: str
    arrive_ms: int
    leave_ms: int


@dataclass(frozen=True)
class ScriptObject:
    key: str
    object_class: ObjectClass
    is_target: bool
    stops: tuple[Stop, ...]


@dataclass(frozen=True)
class ScriptEvent:
    ts_ms: int
    node: str
    type: EventType
    object_class: ObjectClass
    local_track_id: str
    # Ground truth, for the evaluation only: never posted (D-70).
    object_key: str = field(compare=False)
    visit: int = field(compare=False)
    dwell: int | None = field(default=None, compare=False)

    @property
    def ts(self) -> datetime:
        return from_ms(self.ts_ms)

    def sort_key(self) -> tuple[int, str, int]:
        return self.ts_ms, self.local_track_id, TYPE_RANK[self.type]


@dataclass(frozen=True)
class Script:
    objects: tuple[ScriptObject, ...]
    events: tuple[ScriptEvent, ...]
    """The whole night, in posting order."""
    window_start: datetime
    window_end: datetime

    def live_events(self) -> list[ScriptEvent]:
        """The live window (D-71): every stop that starts inside it, cut at its end."""
        start, end = to_ms(self.window_start), to_ms(self.window_end)
        starts = {
            (event.object_key, event.visit): event.ts_ms
            for event in self.events
            if event.type == "appear"
        }
        return [
            event
            for event in self.events
            if start <= starts[event.object_key, event.visit] < end and event.ts_ms < end
        ]

    def find(self, ref: EventRef) -> ScriptEvent:
        """The event a truth reference points at."""
        for event in self.events:
            if (event.object_key, event.visit, event.type) == (
                ref.target,
                ref.visit,
                ref.type,
            ) and (ref.type != "dwell" or event.dwell == ref.n):
                return event
        raise LookupError(f"no event for {ref}")


def target_object(target: Target, clock: NightClock) -> ScriptObject:
    stops: list[Stop] = []
    for visit in target.visits:
        if visit.at is not None:
            arrive = to_ms(clock.at(visit.at))
        else:
            assert visit.after_s is not None  # the file validator guarantees it
            arrive = stops[-1].leave_ms + round(visit.after_s * 1000)
        stops.append(Stop(visit.node, arrive, arrive + round(visit.stay_s * 1000)))
    return ScriptObject(target.key, target.object_class, True, tuple(stops))


def background_objects(
    scenario: ScenarioFile, graph: Graph, clock: NightClock
) -> list[ScriptObject]:
    """Trips along normal routes, hour by hour through the night, from the file's seed."""
    rng = random.Random(scenario.background.seed)
    routes = graph.normal_routes
    trips: list[tuple[int, ObjectClass, list[Stop]]] = []
    hours = sorted(
        scenario.background.trips_per_hour.items(), key=lambda item: night_order(item[0])
    )
    for hour, count in hours:
        hour_ms = to_ms(clock.hour_start(int(hour)))
        for _ in range(count):
            start = hour_ms + round(rng.uniform(0, 3600) * 1000)
            object_class: ObjectClass = (
                "vehicle" if rng.random() < scenario.background.vehicle_share else "person"
            )
            route = rng.choice(routes)
            stops: list[Stop] = []
            moment = start
            for index, node in enumerate(route):
                if index > 0:
                    edge = graph.edge(route[index - 1], node)
                    assert edge is not None  # check_scenario rejects unlinked routes
                    if object_class == "vehicle":
                        travel = rng.uniform(*VEHICLE_TRAVEL_SHARE) * edge.travel_min_s
                    else:
                        travel = rng.uniform(edge.travel_min_s, edge.travel_max_s)
                    moment += round(travel * 1000)
                stay = round(rng.uniform(*STAY_S[object_class]) * 1000)
                stops.append(Stop(node, moment, moment + stay))
                moment += stay
            trips.append((start, object_class, stops))
    trips.sort(key=lambda trip: trip[0])
    return [
        ScriptObject(f"bg-{number:03d}", object_class, False, tuple(stops))
        for number, (_, object_class, stops) in enumerate(trips, start=1)
    ]


def night_order(hour: str) -> int:
    """Evening hours first, then the small hours: 18 → 18, 02 → 26."""
    return int(hour) + (24 if int(hour) < 12 else 0)


def object_events(objects: list[ScriptObject], start_ms: int, end_ms: int) -> list[ScriptEvent]:
    """The events every object sends inside [start, end), with per-camera local track IDs."""
    stops = sorted(
        (
            (stop.arrive_ms, obj.key, index, obj, stop)
            for obj in objects
            for index, stop in enumerate(obj.stops)
            if start_ms <= stop.arrive_ms < end_ms
        ),
        key=lambda item: (item[0], item[1]),
    )
    counters: dict[str, int] = {}
    events: list[ScriptEvent] = []
    for _, key, index, obj, stop in stops:
        counters[stop.node] = counters.get(stop.node, 0) + 1
        local_id = f"{stop.node}#{counters[stop.node]}"
        times: list[tuple[int, EventType, int | None]] = [(stop.arrive_ms, "appear", None)]
        dwell = 1
        while stop.arrive_ms + dwell * DWELL_EVERY_MS < stop.leave_ms:
            times.append((stop.arrive_ms + dwell * DWELL_EVERY_MS, "dwell", dwell))
            dwell += 1
        times.append((stop.leave_ms, "disappear", None))
        events += [
            ScriptEvent(ts_ms, stop.node, kind, obj.object_class, local_id, key, index, number)
            for ts_ms, kind, number in times
        ]
    kept = [event for event in events if event.ts_ms < end_ms]
    return sorted(kept, key=ScriptEvent.sort_key)


def build_script(scenario: ScenarioFile, graph: Graph, timezone: str) -> Script:
    clock = NightClock(scenario.night, timezone)
    objects = [target_object(target, clock) for target in scenario.targets]
    objects += background_objects(scenario, graph, clock)
    events = object_events(objects, to_ms(clock.start), to_ms(clock.end))
    return Script(
        objects=tuple(objects),
        events=tuple(events),
        window_start=clock.at(scenario.live_window.start),
        window_end=clock.at(scenario.live_window.end),
    )
