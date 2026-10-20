"""M4.3: the nearest on-duty guard, escalation, and the next camera with its basis (F5)."""

from app.engine.graph import Graph, GraphNode, LinkData
from app.engine.router import GuardPost, NextCameraWeights, assign, next_camera
from app.sim.golden import seeded_graph


def cross() -> Graph:
    """A crossroads: m in the middle, n north, s south, e east, w west; w → m is one-way."""
    nodes = [
        GraphNode("m", "camera", 100, 100),
        GraphNode("n", "camera", 100, 0),
        GraphNode("s", "camera", 100, 200),
        GraphNode("e", "camera", 200, 100),
        GraphNode("w", "camera", 0, 100),
    ]
    links = [
        LinkData("m", "n", 10, 20, distance_m=20),
        LinkData("m", "s", 30, 40, distance_m=50),
        LinkData("m", "e", 10, 20, distance_m=20),
        LinkData("w", "m", 50, 70, bidirectional=False, distance_m=80),
    ]
    return Graph.build(nodes, links, [("w", "m", "s"), ("n", "m", "s"), ("n", "m", "e")])


def test_the_nearest_on_duty_guard_gets_the_alert() -> None:
    guards = [
        GuardPost("u-guard-01", "n", on_duty=True),  # n → m → s: 15 + 35 = 50 s
        GuardPost("u-guard-02", "e", on_duty=True),  # e → m → s: 15 + 35 = 50 s, tie
        GuardPost("u-guard-03", "s", on_duty=False),  # already there, but off duty
    ]
    result = assign(cross(), guards, "s")
    assert (result.guard, result.walk_s) == ("u-guard-01", 50.0)


def test_a_guard_walks_a_one_way_link_both_ways() -> None:
    result = assign(cross(), [GuardPost("u-guard-01", "m", on_duty=True)], "w")
    assert (result.guard, result.walk_s) == ("u-guard-01", 60.0)


def test_with_no_guard_on_duty_the_alert_escalates() -> None:
    guards = [GuardPost("u-guard-01", "n", on_duty=False), GuardPost("u-guard-02", None, True)]
    result = assign(cross(), guards, "s")
    assert (result.guard, result.walk_s) == (None, None)


def test_the_next_camera_follows_the_direction_of_travel_with_its_basis() -> None:
    # Heading south from n into m: s lies straight ahead, so it wins over e and back to n.
    suggestion = next_camera(cross(), ["n", "m"])
    assert suggestion is not None
    assert suggestion.node == "s"
    assert (suggestion.walk_s, suggestion.distance_m) == (35.0, 50)
    assert suggestion.direction == 1.0
    assert suggestion.transition_share == round(2 / 3, 3)
    assert suggestion.backtrack is False


def test_the_next_camera_avoids_turning_straight_back() -> None:
    # Coming north from s, with no normal route leaving m for n: n still beats going back.
    weights = NextCameraWeights(route_share=0)
    suggestion = next_camera(cross(), ["s", "m"], weights)
    assert suggestion is not None
    assert suggestion.node == "n"
    back = next_camera(cross(), ["s", "m"], NextCameraWeights(direction=0, walk=0, route_share=0))
    assert back is not None and back.node != "s"


def test_the_next_camera_without_a_last_step_leans_on_routes_and_walk() -> None:
    suggestion = next_camera(cross(), ["m"])
    assert suggestion is not None
    assert (suggestion.node, suggestion.direction) == ("s", 0.0)


def test_there_is_no_next_camera_from_a_dead_end_or_an_unknown_node() -> None:
    graph = cross()
    graph.edges["n"] = {}
    assert next_camera(graph, ["m", "n"]) is None
    assert next_camera(graph, ["gone"]) is None
    assert next_camera(graph, []) is None


def node_after(graph: Graph, *path: str) -> str:
    suggestion = next_camera(graph, path)
    assert suggestion is not None
    return suggestion.node


def test_on_the_seeded_layout_the_scenario_targets_go_where_the_score_says() -> None:
    graph = seeded_graph()
    # S2: over the north fence, into the back lane, then lane 2 north, then the main road.
    assert node_after(graph, "s-fence-n") == "c-back-02"
    assert node_after(graph, "s-fence-n", "c-back-02") == "c-lane-2n"
    assert node_after(graph, "s-fence-n", "c-back-02", "c-lane-2n") == "c-main-02"
    # S1: eastbound along the south cross lane.
    assert node_after(graph, "c-lane-1s", "c-lane-2s") == "c-lane-3s"
    posts = [GuardPost("u-guard-01", "c-gate-01", True), GuardPost("u-guard-02", "c-main-02", True)]
    assert assign(graph, posts, "c-lane-2s").guard == "u-guard-02"
