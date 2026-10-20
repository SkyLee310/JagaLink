"""Path linker (F3): joins per-camera sightings into anonymous tracks (D-17, D-55, D-56).

Pure: sightings in, track changes out, with no database, network or wall clock (D-32). The caller
feeds a run's events in ingest order, and event time alone moves the tracks on (D-31), so a
scenario links the same way on every run (D-27). Only the object class and timing count, never
how an object looks (D-09).

An object that leaves node A can join at a linked node B within
[exit + travel_min_s × class factor, exit + travel_max_s]; when several tracks fit one
appearance, the one whose travel time sits closest to the middle of its window wins. Anything
else starts a new track. A track closes once no linked node can still see it, and expires
`ttl_s` after its last sighting.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal

from app.engine.events import EventType, ObjectClass
from app.engine.graph import Graph

TrackStatus = Literal["active", "closed", "expired"]

DEFAULT_TTL_S = 24 * 3600
"""D-56: a track expires 24 h after its last sighting; config can shorten it for the demo."""


@dataclass(frozen=True)
class Sighting:
    """One event as the linker reads it; nodes are codes (D-75)."""

    id: str
    ts: datetime
    node: str
    type: EventType
    object_class: ObjectClass
    local_track_id: str


@dataclass
class Segment:
    """A track's stay in front of one node, from its appear to its disappear."""

    node: str
    enter: datetime
    exit: datetime | None = None
    event_ids: list[str] = field(default_factory=list)


@dataclass
class Track:
    number: int
    """Order of creation within the run, from 1."""
    object_class: ObjectClass
    segments: list[Segment]
    first_ts: datetime
    last_ts: datetime
    expires_at: datetime
    status: TrackStatus = "active"

    @property
    def head(self) -> Segment:
        return self.segments[-1]

    @property
    def waiting(self) -> bool:
        """Out of view, and a linked node may still see it next."""
        return self.status == "active" and self.head.exit is not None

    def nodes(self) -> list[str]:
        return [segment.node for segment in self.segments]

    def event_ids(self) -> list[str]:
        return [event_id for segment in self.segments for event_id in segment.event_ids]


@dataclass
class Changes:
    """What one call changed: tracks to write, and tracks to delete."""

    updated: dict[int, Track] = field(default_factory=dict)
    expired: dict[int, Track] = field(default_factory=dict)

    def touch(self, track: Track) -> None:
        self.updated[track.number] = track

    def merge(self, other: "Changes") -> "Changes":
        for number in other.expired:
            self.updated.pop(number, None)
        self.updated.update(other.updated)
        self.expired.update(other.expired)
        return self


class Linker:
    def __init__(self, graph: Graph, ttl_s: float = DEFAULT_TTL_S) -> None:
        self.graph = graph
        self.ttl = timedelta(seconds=ttl_s)
        self.tracks: dict[int, Track] = {}
        """Every track that has not expired, by number."""
        self.in_view: dict[tuple[str, str], int] = {}
        """(node, local track ID) of each sighting still in view → its track number."""
        self.created = 0

    def feed(self, sighting: Sighting) -> Changes:
        """Add one event; events must come in time order."""
        changes = self.advance(sighting.ts)
        changes.touch(self._place(sighting))
        return changes

    def advance(self, now: datetime) -> Changes:
        """Move event time on to `now`: close tracks no node can still see, and expire tracks
        past their TTL (D-56)."""
        changes = Changes()
        for track in list(self.tracks.values()):
            if track.expires_at <= now:
                self._drop(track)
                changes.expired[track.number] = track
            elif track.waiting and self._deadline(track) < now:
                track.status = "closed"
                changes.touch(track)
        return changes

    def finish(self) -> Changes:
        """The run has ended: no later sighting can join any track, so every one closes."""
        changes = Changes()
        for track in self.tracks.values():
            if track.status == "active":
                track.status = "closed"
                changes.touch(track)
        self.in_view.clear()
        return changes

    def _place(self, sighting: Sighting) -> Track:
        key = (sighting.node, sighting.local_track_id)
        number = self.in_view.get(key)
        track = self.tracks.get(number) if number is not None else None
        if sighting.type == "appear" or track is None:
            # A dwell or disappear with no appear before it was seen mid-stay: a new track.
            joined = self._best_join(sighting) if sighting.type == "appear" else None
            if joined is None:
                track = self._open(sighting)
            else:
                track = joined
                track.segments.append(Segment(sighting.node, sighting.ts, None, [sighting.id]))
            self.in_view[key] = track.number
        else:
            track.head.event_ids.append(sighting.id)
        if sighting.type == "disappear":
            track.head.exit = sighting.ts
            self.in_view.pop(key, None)
        track.last_ts = sighting.ts
        track.expires_at = sighting.ts + self.ttl
        return track

    def _open(self, sighting: Sighting) -> Track:
        self.created += 1
        track = Track(
            number=self.created,
            object_class=sighting.object_class,
            segments=[Segment(sighting.node, sighting.ts, None, [sighting.id])],
            first_ts=sighting.ts,
            last_ts=sighting.ts,
            expires_at=sighting.ts + self.ttl,
        )
        self.tracks[track.number] = track
        return track

    def _best_join(self, sighting: Sighting) -> Track | None:
        """The waiting track this appearance continues, if any (D-17): same class, a link from
        its last node, inside the class's time window (D-55); the best time fit wins."""
        best: tuple[float, int] | None = None
        chosen: Track | None = None
        for track in self.tracks.values():
            if not track.waiting or track.object_class != sighting.object_class:
                continue
            edge = self.graph.edge(track.head.node, sighting.node)
            if edge is None:
                continue
            low, high = edge.window(sighting.object_class)
            assert track.head.exit is not None  # a waiting track has left its node
            elapsed = (sighting.ts - track.head.exit).total_seconds()
            if not low <= elapsed <= high:
                continue
            misfit = abs(elapsed - (low + high) / 2) / max(high - low, 1e-9)
            if best is None or (misfit, track.number) < best:
                best, chosen = (misfit, track.number), track
        return chosen

    def _deadline(self, track: Track) -> datetime:
        """The last moment a linked node could still see this waiting track."""
        assert track.head.exit is not None
        reach = max(
            (edge.travel_max_s for edge in self.graph.edges.get(track.head.node, {}).values()),
            default=0,
        )
        return track.head.exit + timedelta(seconds=reach)

    def _drop(self, track: Track) -> None:
        track.status = "expired"
        del self.tracks[track.number]
        for key in [key for key, number in self.in_view.items() if number == track.number]:
            del self.in_view[key]


def link_all(
    graph: Graph, sightings: Iterable[Sighting], ttl_s: float = DEFAULT_TTL_S
) -> list[Track]:
    """Link a whole run and close it: every track it made, in creation order (golden files,
    evaluation)."""
    linker = Linker(graph, ttl_s)
    seen: dict[int, Track] = {}
    for sighting in sightings:
        changes = linker.feed(sighting)
        seen.update(changes.updated)
        seen.update(changes.expired)
    seen.update(linker.finish().updated)
    return [seen[number] for number in sorted(seen)]
