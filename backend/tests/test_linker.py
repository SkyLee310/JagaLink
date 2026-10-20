"""M3.1: the path linker joins sightings inside the walking window and nothing else (D-17)."""

from datetime import UTC, datetime, timedelta

from app.engine.events import EventType, ObjectClass
from app.engine.graph import Graph, GraphNode, LinkData
from app.engine.linker import Linker, Sighting, link_all

T0 = datetime(2026, 10, 21, 18, 0, tzinfo=UTC)

# a ─(20-40 s)─ b ─(10-15 s)─ c, a one-way link a → d, and e on its own.
GRAPH = Graph.build(
    [GraphNode(code, "camera", float(x), 0.0) for x, code in enumerate("abcde")],
    [
        LinkData("a", "b", 20, 40),
        LinkData("b", "c", 10, 15),
        LinkData("a", "d", 20, 40, bidirectional=False),
    ],
)


def at(seconds: float) -> datetime:
    return T0 + timedelta(seconds=seconds)


class Stream:
    """Builds sightings with unique event and per-camera IDs, like a source would post them."""

    def __init__(self) -> None:
        self.count = 0

    def stay(
        self, node: str, arrive: float, leave: float, object_class: ObjectClass = "person"
    ) -> list[Sighting]:
        self.count += 1
        local = f"{node}#{self.count}"
        return [
            self.event(node, arrive, "appear", object_class, local),
            self.event(node, leave, "disappear", object_class, local),
        ]

    def event(
        self, node: str, second: float, kind: EventType, object_class: ObjectClass, local: str
    ) -> Sighting:
        self.count += 1
        return Sighting(f"e{self.count}", at(second), node, kind, object_class, local)


def link(*stays: list[Sighting], ttl_s: float = 3600) -> list[list[str]]:
    """Feed the stays in time order; each track's nodes, in creation order."""
    sightings = sorted((s for stay in stays for s in stay), key=lambda s: s.ts)
    return [track.nodes() for track in link_all(GRAPH, sightings, ttl_s)]


def test_an_appearance_inside_the_window_joins_the_track() -> None:
    s = Stream()
    assert link(s.stay("a", 0, 5), s.stay("b", 35, 40), s.stay("c", 52, 55)) == [["a", "b", "c"]]


def test_the_window_edges_still_join() -> None:
    s = Stream()
    assert link(s.stay("a", 0, 5), s.stay("b", 25, 30)) == [["a", "b"]]
    s = Stream()
    assert link(s.stay("a", 0, 5), s.stay("b", 45, 50)) == [["a", "b"]]


def test_too_early_or_too_late_starts_a_new_track() -> None:
    s = Stream()
    assert link(s.stay("a", 0, 5), s.stay("b", 24.9, 30)) == [["a"], ["b"]]
    s = Stream()
    assert link(s.stay("a", 0, 5), s.stay("b", 45.1, 50)) == [["a"], ["b"]]


def test_an_unlinked_camera_starts_a_new_track() -> None:
    s = Stream()
    assert link(s.stay("a", 0, 5), s.stay("e", 30, 35)) == [["a"], ["e"]]


def test_a_one_way_link_joins_in_its_direction_only() -> None:
    s = Stream()
    assert link(s.stay("a", 0, 5), s.stay("d", 30, 35)) == [["a", "d"]]
    s = Stream()
    assert link(s.stay("d", 0, 5), s.stay("a", 30, 35)) == [["d"], ["a"]]


def test_a_different_object_class_never_joins() -> None:
    s = Stream()
    assert link(s.stay("a", 0, 5, "person"), s.stay("b", 35, 40, "vehicle")) == [["a"], ["b"]]


def test_a_vehicle_may_arrive_sooner_than_walking_time() -> None:
    # D-55: a vehicle's window on a 20-40 s link opens at 0.3 × 20 = 6 s.
    s = Stream()
    assert link(s.stay("a", 0, 5, "vehicle"), s.stay("b", 13, 15, "vehicle")) == [["a", "b"]]
    s = Stream()
    assert link(s.stay("a", 0, 5, "person"), s.stay("b", 13, 15, "person")) == [["a"], ["b"]]


def test_competing_objects_each_join_their_best_time_fit() -> None:
    # Two people leave a at 0 s and 10 s. At 30 s only the first is mid-window (30 of 20-40);
    # the second (20 s) would sit on the window's edge, so it waits for the 40 s appearance.
    s = Stream()
    first, second = s.stay("a", -5, 0), s.stay("a", 5, 10)
    sightings = sorted(
        [*first, *second, *s.stay("b", 30, 31), *s.stay("b", 40, 41)], key=lambda x: x.ts
    )
    tracks = link_all(GRAPH, sightings)
    assert [track.nodes() for track in tracks] == [["a", "b"], ["a", "b"]]
    assert tracks[0].segments[1].enter == at(30)
    assert tracks[1].segments[1].enter == at(40)


def test_dwell_events_stay_on_the_segment_in_view() -> None:
    s = Stream()
    appear = s.event("a", 0, "appear", "person", "a#1")
    dwell = s.event("a", 60, "dwell", "person", "a#1")
    leave = s.event("a", 90, "disappear", "person", "a#1")
    [track] = link_all(GRAPH, [appear, dwell, leave])
    assert track.segments[0].event_ids == [appear.id, dwell.id, leave.id]
    assert (track.segments[0].enter, track.segments[0].exit) == (at(0), at(90))


def test_a_sighting_seen_mid_stay_starts_its_own_track() -> None:
    s = Stream()
    dwell = s.event("b", 60, "dwell", "person", "b#7")
    leave = s.event("b", 70, "disappear", "person", "b#7")
    [track] = link_all(GRAPH, [dwell, leave])
    assert track.nodes() == ["b"]
    assert track.segments[0].event_ids == [dwell.id, leave.id]


def test_a_waiting_track_closes_after_its_longest_outgoing_walk() -> None:
    # From b the longest link is 40 s (back to a): the track waits until exit + 40 s.
    s = Stream()
    linker = Linker(GRAPH)
    for sighting in s.stay("b", 0, 5):
        linker.feed(sighting)
    assert linker.advance(at(45)).updated == {}
    [closed] = linker.advance(at(45.001)).updated.values()
    assert closed.status == "closed"
    # A closed track takes nothing more: a late appearance at c starts a new track.
    for sighting in s.stay("c", 50, 52):
        linker.feed(sighting)
    assert [track.nodes() for track in linker.tracks.values()] == [["b"], ["c"]]


def test_a_track_in_view_never_closes() -> None:
    linker = Linker(GRAPH)
    linker.feed(Stream().event("a", 0, "appear", "person", "a#1"))
    assert linker.advance(at(600)).updated == {}
    assert linker.tracks[1].status == "active"


def test_a_track_expires_its_ttl_after_its_last_sighting() -> None:
    s = Stream()
    linker = Linker(GRAPH, ttl_s=30)
    for sighting in s.stay("a", 0, 5):
        linker.feed(sighting)
    assert linker.tracks[1].expires_at == at(35)
    assert linker.advance(at(34.999)).expired == {}
    [expired] = linker.advance(at(35)).expired.values()
    assert expired.status == "expired"
    assert linker.tracks == {}


def test_finish_closes_every_active_track() -> None:
    s = Stream()
    linker = Linker(GRAPH)
    linker.feed(s.event("a", 0, "appear", "person", "a#1"))
    for sighting in s.stay("c", 0, 3):
        linker.feed(sighting)
    finished = linker.finish()
    assert sorted(finished.updated) == [1, 2]
    assert {track.status for track in linker.tracks.values()} == {"closed"}


def test_linking_is_deterministic() -> None:
    s = Stream()
    sightings = sorted(
        [*s.stay("a", 0, 5), *s.stay("a", 2, 6), *s.stay("b", 30, 33), *s.stay("b", 31, 35)],
        key=lambda x: x.ts,
    )
    first = [(t.number, t.nodes(), t.event_ids()) for t in link_all(GRAPH, sightings)]
    again = [(t.number, t.nodes(), t.event_ids()) for t in link_all(GRAPH, sightings)]
    assert first == again
