"""The camera graph the engine works on: nodes and walking-time links, keyed by node code.

Built from a layout file (seed, export) or from the database's layout, so the scripts, the
linker, the rules and the router all read one shape (D-75: references are codes).
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Literal

from app.engine.events import ObjectClass

# D-55: link times are walking times; a vehicle may arrive sooner, down to this share of
# travel_min_s. travel_max_s stays as it is.
CLASS_FACTOR: dict[ObjectClass, float] = {"person": 1.0, "vehicle": 0.3}


@dataclass(frozen=True)
class GraphNode:
    code: str
    kind: Literal["camera", "sensor"]
    x: float
    y: float
    zone: str | None = None
    zone_kind: Literal["street", "gate", "lane"] | None = None
    online: bool = True


@dataclass(frozen=True)
class Edge:
    """One direction of a link."""

    start: str
    end: str
    travel_min_s: int
    travel_max_s: int
    distance_m: float | None = None

    def window(self, object_class: ObjectClass) -> tuple[float, float]:
        """Seconds after leaving `start` in which an object of this class can reach `end`."""
        return self.travel_min_s * CLASS_FACTOR[object_class], float(self.travel_max_s)


@dataclass(frozen=True)
class LinkData:
    start: str
    end: str
    travel_min_s: int
    travel_max_s: int
    bidirectional: bool = True
    distance_m: float | None = None


@dataclass
class Graph:
    nodes: dict[str, GraphNode]
    edges: dict[str, dict[str, Edge]] = field(default_factory=dict)
    normal_routes: list[tuple[str, ...]] = field(default_factory=list)

    @classmethod
    def build(
        cls,
        nodes: Iterable[GraphNode],
        links: Iterable[LinkData],
        normal_routes: Iterable[Sequence[str]] = (),
    ) -> "Graph":
        graph = cls(nodes={node.code: node for node in nodes})
        graph.edges = {code: {} for code in graph.nodes}
        for link in links:
            ends = [(link.start, link.end)]
            if link.bidirectional:
                ends.append((link.end, link.start))
            for start, end in ends:
                graph.edges[start][end] = Edge(
                    start, end, link.travel_min_s, link.travel_max_s, link.distance_m
                )
        graph.normal_routes = [tuple(route) for route in normal_routes]
        return graph

    def edge(self, start: str, end: str) -> Edge | None:
        return self.edges.get(start, {}).get(end)

    def neighbours(self, code: str) -> list[str]:
        """Nodes reachable from this one in one link, in code order."""
        return sorted(self.edges.get(code, {}))

    def normal_transitions(self) -> set[tuple[str, str]]:
        """Every (from, to) step that some normal route takes (D-53)."""
        return {
            (route[i], route[i + 1]) for route in self.normal_routes for i in range(len(route) - 1)
        }
