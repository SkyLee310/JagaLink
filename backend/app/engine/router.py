"""Alert routing and the next-camera suggestion (F5, D-19, D-20, D-57, D-58).

Pure: the camera graph and guard posts in, an assignment or a suggestion out (D-32). Guards walk,
so routing reads every link both ways; an object follows the links, so the next camera is one the
track's current node links to. The suggestion never reads the scenario's true path (D-57).
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass

import networkx as nx

from app.engine.graph import Graph


@dataclass(frozen=True)
class GuardPost:
    """Where a guard stands for the run (D-58); `node` is a code, None when off post."""

    code: str
    node: str | None
    on_duty: bool


@dataclass(frozen=True)
class Assignment:
    guard: str | None
    """The nearest on-duty guard's user code; None escalates the alert to the supervisor."""
    walk_s: float | None
    """That guard's walking time to the alert's node, in seconds."""


@dataclass(frozen=True)
class NextCameraWeights:
    """How the next-camera score weighs each factor (D-57); config may change them."""

    direction: float = 1.0
    backtrack: float = 2.0
    walk: float = 0.5
    route_share: float = 1.0


@dataclass(frozen=True)
class Suggestion:
    """The most likely next node and the basis behind it (D-20)."""

    node: str
    walk_s: float
    distance_m: float | None
    transition_share: float
    """Share of the normal routes leaving the current node that take this step (D-53)."""
    direction: float
    """Cosine between the track's last step and this one; 0 when there is no last step."""
    backtrack: bool
    score: float


def link_walk_s(travel_min_s: float, travel_max_s: float) -> float:
    """D-58: one weight per link, the middle of its walking window."""
    return (travel_min_s + travel_max_s) / 2


def walking_graph(graph: Graph) -> nx.Graph:
    """Every link as a two-way path for a guard on foot, weighted by its walking time."""
    walk = nx.Graph()
    walk.add_nodes_from(graph.nodes)
    for start, edges in graph.edges.items():
        for end, edge in edges.items():
            weight = link_walk_s(edge.travel_min_s, edge.travel_max_s)
            if not walk.has_edge(start, end) or weight < walk[start][end]["weight"]:
                walk.add_edge(start, end, weight=weight)
    return walk


def assign(graph: Graph, guards: Sequence[GuardPost], node: str) -> Assignment:
    """The on-duty guard with the shortest walk to `node` (Dijkstra, D-19); ties go to the
    lower user code. With nobody on duty who can reach it, the alert escalates."""
    walk = walking_graph(graph)
    if node not in walk:
        return Assignment(None, None)
    times = nx.single_source_dijkstra_path_length(walk, node, weight="weight")
    reachable = [
        (float(times[guard.node]), guard.code)
        for guard in guards
        if guard.on_duty and guard.node is not None and guard.node in times
    ]
    if not reachable:
        return Assignment(None, None)
    walk_s, code = min(reachable)
    return Assignment(code, walk_s)


def next_camera(
    graph: Graph, path: Sequence[str], weights: NextCameraWeights | None = None
) -> Suggestion | None:
    """Score each node the track's current node links to (D-57): the direction of travel,
    no immediate backtrack, a short walk, and the step's share of the normal routes."""
    weights = weights or NextCameraWeights()
    if not path or path[-1] not in graph.nodes:
        return None
    current = path[-1]
    previous = path[-2] if len(path) >= 2 and path[-2] in graph.nodes else None
    edges = graph.edges.get(current, {})
    if not edges:
        return None
    walks = {end: link_walk_s(edge.travel_min_s, edge.travel_max_s) for end, edge in edges.items()}
    longest = max(walks.values())
    shares = _route_shares(graph, current)
    here = graph.nodes[current]
    heading = None
    if previous is not None:
        before = graph.nodes[previous]
        heading = (here.x - before.x, here.y - before.y)

    suggestions = []
    for end, edge in sorted(edges.items()):
        there = graph.nodes[end]
        direction = _cosine(heading, (there.x - here.x, there.y - here.y)) if heading else 0.0
        backtrack = end == previous
        share = shares.get(end, 0.0)
        score = (
            weights.direction * direction
            - weights.backtrack * backtrack
            + weights.walk * (1 - walks[end] / longest)
            + weights.route_share * share
        )
        suggestions.append(
            Suggestion(
                node=end,
                walk_s=walks[end],
                distance_m=edge.distance_m,
                transition_share=round(share, 3),
                direction=round(direction, 3),
                backtrack=backtrack,
                score=round(score, 3),
            )
        )
    # The highest score wins; ties go to the lower node code.
    return min(suggestions, key=lambda s: (-s.score, s.node))


def _route_shares(graph: Graph, current: str) -> dict[str, float]:
    steps = [
        route[i + 1]
        for route in graph.normal_routes
        for i in range(len(route) - 1)
        if route[i] == current
    ]
    return {end: steps.count(end) / len(steps) for end in set(steps)}


def _cosine(a: tuple[float, float], b: tuple[float, float]) -> float:
    length = math.hypot(*a) * math.hypot(*b)
    if length == 0:
        return 0.0
    return (a[0] * b[0] + a[1] * b[1]) / length
