"""F1 layout rules (D-14, D-39, D-65), shared by the API and the layout file.

Nodes and links are identified by a key: a database ID in the API, a code in a file. Messages
name nodes by code, so they read the same in both.
"""

from collections import Counter
from collections.abc import Hashable, Iterable, Sequence
from dataclasses import dataclass
from typing import Literal

ProblemCode = Literal[
    "duplicate_node",
    "duplicate_code",
    "unknown_zone",
    "self_link",
    "unknown_node",
    "travel_window",
    "duplicate_link",
]

# A duplicate collides with something that already exists (409); the rest is malformed (422).
CONFLICTS: frozenset[ProblemCode] = frozenset({"duplicate_code", "duplicate_link"})


@dataclass(frozen=True)
class NodeSpec:
    key: Hashable
    code: str
    zone: Hashable | None = None


@dataclass(frozen=True)
class LinkSpec:
    from_key: Hashable
    to_key: Hashable
    travel_min_s: int
    travel_max_s: int
    bidirectional: bool = True


@dataclass(frozen=True)
class Problem:
    code: ProblemCode
    message: str


def same_link(a: LinkSpec, b: LinkSpec) -> bool:
    """D-65: (A, B) and (B, A) are one link when either is bidirectional."""
    if (a.from_key, a.to_key) == (b.from_key, b.to_key):
        return True
    reverse = (a.from_key, a.to_key) == (b.to_key, b.from_key)
    return reverse and (a.bidirectional or b.bidirectional)


def check_layout(
    nodes: Sequence[NodeSpec], links: Sequence[LinkSpec], zones: Iterable[Hashable]
) -> list[Problem]:
    """Every problem in a layout, in a stable order; an empty list means it is valid."""
    problems: list[Problem] = []
    known_zones = set(zones)
    codes = {node.key: node.code for node in nodes}

    for key, count in Counter(node.key for node in nodes).items():
        if count > 1:
            problems.append(Problem("duplicate_node", f"node {codes[key]} appears {count} times"))
    for code, count in Counter(node.code for node in nodes).items():
        if count > 1:
            problems.append(Problem("duplicate_code", f"duplicate node code {code}"))
    for node in nodes:
        if node.zone is not None and node.zone not in known_zones:
            problems.append(
                Problem("unknown_zone", f"node {node.code} names unknown zone {node.zone}")
            )

    kept: list[LinkSpec] = []
    for link in links:
        start, end = codes.get(link.from_key, link.from_key), codes.get(link.to_key, link.to_key)
        label = f"link {start} -> {end}"
        if link.from_key == link.to_key:
            problems.append(Problem("self_link", f"{label} joins a node to itself"))
        for key, code in ((link.from_key, start), (link.to_key, end)):
            if key not in codes:
                problems.append(Problem("unknown_node", f"{label} names unknown node {code}"))
        if link.travel_min_s <= 0:
            problems.append(Problem("travel_window", f"{label} needs travel_min_s above 0"))
        if link.travel_min_s > link.travel_max_s:
            problems.append(
                Problem("travel_window", f"{label} has travel_min_s above travel_max_s")
            )
        if any(same_link(link, other) for other in kept):
            problems.append(Problem("duplicate_link", f"{label} duplicates another link"))
        kept.append(link)
    return problems


def status_for(problems: Sequence[Problem]) -> int:
    """409 when every problem is a duplicate (D-40), else 422."""
    return 409 if all(problem.code in CONFLICTS for problem in problems) else 422
