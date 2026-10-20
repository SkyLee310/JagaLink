import json
import math
from collections import deque
from collections.abc import Callable
from typing import Any

import pytest
from pydantic import ValidationError

from app.db.seed import DEFAULT_LAYOUT
from app.schemas.layout import LayoutFile

RAW = DEFAULT_LAYOUT.read_text(encoding="utf-8")
LAYOUT = LayoutFile.model_validate_json(RAW)  # loading it is the validity check


def test_seed_layout_matches_d69() -> None:
    assert len(LAYOUT.nodes) == 20
    assert {node.kind for node in LAYOUT.nodes} == {"camera", "sensor"}
    assert [zone.kind for zone in LAYOUT.zones].count("gate") == 1


def test_walking_times_match_distances() -> None:
    """D-69: min = floor(d / 1.4 m/s), max = ceil(d / 1.2 m/s), d along the streets."""
    nodes = {node.code: node for node in LAYOUT.nodes}
    scale = LAYOUT.community.scale_m_per_px
    for link in LAYOUT.links:
        assert link.distance_m is not None, link
        assert link.travel_min_s == math.floor(link.distance_m / 1.4 + 1e-9), link
        assert link.travel_max_s == math.ceil(link.distance_m / 1.2 - 1e-9), link
        start, end = nodes[link.from_node], nodes[link.to_node]
        straight_m = math.dist((start.x, start.y), (end.x, end.y)) * scale
        assert link.distance_m >= straight_m - 1e-6, f"{link} is shorter than a straight line"


def _reachable(start: str, edges: list[tuple[str, str]]) -> set[str]:
    seen, queue = {start}, deque([start])
    while queue:
        here = queue.popleft()
        for a, b in edges:
            if a == here and b not in seen:
                seen.add(b)
                queue.append(b)
    return seen


def test_every_node_connects_to_the_gate() -> None:
    edges = [(link.from_node, link.to_node) for link in LAYOUT.links]
    edges += [(link.to_node, link.from_node) for link in LAYOUT.links if link.bidirectional]
    everyone = set(LAYOUT.node_codes)
    assert _reachable("c-gate-01", edges) == everyone
    assert _reachable("c-gate-02", [(b, a) for a, b in edges]) == everyone


def _add_link(start: str, end: str) -> Callable[[dict[str, Any]], None]:
    def change(data: dict[str, Any]) -> None:
        link = {"from_node": start, "to_node": end, "travel_min_s": 10, "travel_max_s": 20}
        data["links"].append(link)

    return change


def _set(section: str, index: int, field: str, value: Any) -> Callable[[dict[str, Any]], None]:
    def change(data: dict[str, Any]) -> None:
        data[section][index][field] = value

    return change


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (_add_link("c-main-01", "c-main-01"), "joins a node to itself"),
        (_add_link("c-main-01", "c-main-02"), "duplicates another link"),
        (_add_link("c-main-02", "c-main-01"), "duplicates another link"),
        (_add_link("c-main-01", "c-nowhere"), "names unknown node c-nowhere"),
        (_set("nodes", 0, "zone", "z-nowhere"), "names unknown zone z-nowhere"),
        (_set("nodes", 1, "code", "c-gate-01"), "duplicate node code c-gate-01"),
        (_set("links", 0, "travel_min_s", 99), "travel_min_s above travel_max_s"),
    ],
)
def test_broken_layouts_are_rejected(
    change: Callable[[dict[str, Any]], None], message: str
) -> None:
    data = json.loads(RAW)
    change(data)
    with pytest.raises(ValidationError, match=message):
        LayoutFile.model_validate(data)


def test_opposite_one_way_links_are_allowed() -> None:
    data = json.loads(RAW)
    _add_link("c-main-01", "c-gate-01")(data)  # c-gate-01 -> c-main-01 is one-way
    data["links"][-1]["bidirectional"] = False
    LayoutFile.model_validate(data)


def test_normal_routes_walk_along_links() -> None:
    """D-53: each step of a normal route follows a link, in a direction the link allows."""
    allowed = {(link.from_node, link.to_node) for link in LAYOUT.links}
    allowed |= {(link.to_node, link.from_node) for link in LAYOUT.links if link.bidirectional}
    assert LAYOUT.normal_routes
    for route in LAYOUT.normal_routes:
        assert set(zip(route.nodes, route.nodes[1:], strict=False)) <= allowed, route.name


def test_back_lane_and_fences_are_never_normal() -> None:
    """Residents keep off the back lane and the fences at night, so a move there is off-route."""
    on_routes = {code for route in LAYOUT.normal_routes for code in route.nodes}
    assert not {code for code in on_routes if code.startswith(("c-back-", "s-fence-"))}
