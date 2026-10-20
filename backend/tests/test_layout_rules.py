"""M1.1: every rejection of the F1 layout rules, as pure functions."""

import pytest

from app.engine.layout import LinkSpec, NodeSpec, Problem, check_layout, same_link, status_for

NODES = [NodeSpec("a", "c-a", "z-1"), NodeSpec("b", "c-b", "z-1"), NodeSpec("c", "c-c")]
ZONES = {"z-1"}


def link(start: str, end: str, low: int = 10, high: int = 20, both: bool = True) -> LinkSpec:
    return LinkSpec(start, end, low, high, both)


def codes(problems: list[Problem]) -> list[str]:
    return [problem.code for problem in problems]


def test_a_valid_layout_has_no_problems() -> None:
    assert check_layout(NODES, [link("a", "b"), link("b", "c", 5, 5)], ZONES) == []


def test_self_link_is_rejected() -> None:
    problems = check_layout(NODES, [link("a", "a")], ZONES)
    assert problems == [Problem("self_link", "link c-a -> c-a joins a node to itself")]
    assert status_for(problems) == 422


def test_unknown_node_is_rejected() -> None:
    problems = check_layout(NODES, [link("a", "x")], ZONES)
    assert problems == [Problem("unknown_node", "link c-a -> x names unknown node x")]
    assert status_for(problems) == 422


@pytest.mark.parametrize(
    ("low", "high", "message"),
    [
        (30, 20, "has travel_min_s above travel_max_s"),
        (0, 20, "needs travel_min_s above 0"),
        (-5, 20, "needs travel_min_s above 0"),
    ],
)
def test_travel_window_needs_zero_below_min_below_max(low: int, high: int, message: str) -> None:
    problems = check_layout(NODES, [link("a", "b", low, high)], ZONES)
    assert codes(problems) == ["travel_window"]
    assert message in problems[0].message
    assert status_for(problems) == 422


def test_equal_min_and_max_are_allowed() -> None:
    assert check_layout(NODES, [link("a", "b", 15, 15)], ZONES) == []


@pytest.mark.parametrize(
    ("first", "second"),
    [
        (link("a", "b"), link("a", "b", 5, 9)),  # same direction twice
        (link("a", "b"), link("b", "a", both=False)),  # reverse of a two-way link
        (link("a", "b", both=False), link("b", "a")),  # two-way over a one-way
        (link("a", "b", both=False), link("a", "b", both=False)),
    ],
)
def test_duplicate_links_follow_d65(first: LinkSpec, second: LinkSpec) -> None:
    assert same_link(first, second)
    problems = check_layout(NODES, [first, second], ZONES)
    assert problems == [Problem("duplicate_link", f"link {_label(second)} duplicates another link")]
    assert status_for(problems) == 409


def test_opposite_one_way_links_are_two_links() -> None:
    one_way, back = link("a", "b", both=False), link("b", "a", both=False)
    assert not same_link(one_way, back)
    assert check_layout(NODES, [one_way, back], ZONES) == []


def test_duplicate_code_is_a_conflict() -> None:
    problems = check_layout([*NODES, NodeSpec("d", "c-a")], [], ZONES)
    assert problems == [Problem("duplicate_code", "duplicate node code c-a")]
    assert status_for(problems) == 409


def test_unknown_zone_is_rejected() -> None:
    problems = check_layout([NodeSpec("a", "c-a", "z-9")], [], ZONES)
    assert problems == [Problem("unknown_zone", "node c-a names unknown zone z-9")]


def test_the_same_node_twice_is_rejected() -> None:
    problems = check_layout([NodeSpec("a", "c-a"), NodeSpec("a", "c-a")], [], ZONES)
    assert codes(problems) == ["duplicate_node", "duplicate_code"]


def test_a_conflict_mixed_with_a_malformed_link_answers_422() -> None:
    problems = check_layout(NODES, [link("a", "b"), link("a", "b"), link("c", "c")], ZONES)
    assert codes(problems) == ["duplicate_link", "self_link"]
    assert status_for(problems) == 422


def _label(spec: LinkSpec) -> str:
    return f"c-{spec.from_key} -> c-{spec.to_key}"
