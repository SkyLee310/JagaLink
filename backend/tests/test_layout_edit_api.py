"""M1.2: saving a whole layout and editing single nodes and links (F1)."""

from collections.abc import Callable
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db.seed import SeedReport, seed_id

Headers = dict[str, str]
NODE_FIELDS = ("id", "code", "kind", "name", "x", "y", "heading_deg", "status", "zone_id")
LINK_FIELDS = ("from_node_id", "to_node_id", "travel_min_s", "travel_max_s", "bidirectional")


@pytest.fixture
def sup(headers_for: Callable[[str], Headers]) -> Headers:
    return headers_for("u-sup-01")


@pytest.fixture
def guard(headers_for: Callable[[str], Headers]) -> Headers:
    return headers_for("u-guard-02")


def node_id(code: str) -> str:
    return str(seed_id("taman-simulasi", "node", code))


def url(seeded: SeedReport, part: str = "layout") -> str:
    return f"/api/v1/communities/{seeded.community_id}/{part}"


def editable(layout: dict[str, Any]) -> dict[str, Any]:
    """The PUT body for a layout as GET returns it."""
    return {
        "nodes": [{field: node[field] for field in NODE_FIELDS} for node in layout["nodes"]],
        "links": [
            {field: link[field] for field in ("id", *LINK_FIELDS, "distance_m")}
            for link in layout["links"]
        ],
    }


def link_set(links: list[dict[str, Any]]) -> set[tuple[Any, ...]]:
    return {tuple(link[field] for field in LINK_FIELDS) for link in links}


def new_link(start: str, end: str, **fields: Any) -> dict[str, Any]:
    return {
        "from_node_id": start,
        "to_node_id": end,
        "travel_min_s": 10,
        "travel_max_s": 14,
        "bidirectional": True,
        **fields,
    }


def test_a_saved_layout_reads_back_identical(
    client: TestClient, seeded: SeedReport, sup: Headers
) -> None:
    body = editable(client.get(url(seeded), headers=sup).json())
    body["nodes"][0]["x"] += 25  # drag
    body["nodes"][1]["heading_deg"] = 135  # turn
    added = {
        "id": str(uuid4()),
        "code": "c-new-01",
        "kind": "camera",
        "name": "New camera",
        "x": 990.0,
        "y": 460.0,
        "heading_deg": 0,
        "status": "online",
        "zone_id": None,
    }
    body["nodes"].append(added)
    body["links"].append(new_link(node_id("c-main-04"), added["id"]))
    removed = node_id("s-fence-e")
    body["nodes"] = [node for node in body["nodes"] if node["id"] != removed]
    body["links"] = [link for link in body["links"] if removed not in link.values()]

    saved = client.put(url(seeded), json=body, headers=sup)
    assert saved.status_code == 200, saved.json()
    again = client.get(url(seeded), headers=sup).json()
    assert again == saved.json()
    nodes = sorted(body["nodes"], key=lambda node: node["code"])
    assert [{field: n[field] for field in NODE_FIELDS} for n in again["nodes"]] == nodes
    assert link_set(again["links"]) == link_set(body["links"])


def test_saving_keeps_node_ids(client: TestClient, seeded: SeedReport, sup: Headers) -> None:
    body = editable(client.get(url(seeded), headers=sup).json())
    for node in body["nodes"]:
        node["name"] += " (edited)"
    saved = client.put(url(seeded), json=body, headers=sup).json()
    assert {node["id"] for node in saved["nodes"]} == {node["id"] for node in body["nodes"]}


def test_two_nodes_can_swap_codes(client: TestClient, seeded: SeedReport, sup: Headers) -> None:
    body = editable(client.get(url(seeded), headers=sup).json())
    one, two = (
        next(n for n in body["nodes"] if n["code"] == c) for c in ("c-main-01", "c-main-02")
    )
    one["code"], two["code"] = "c-main-02", "c-main-01"
    saved = client.put(url(seeded), json=body, headers=sup)
    assert saved.status_code == 200
    codes = {node["id"]: node["code"] for node in saved.json()["nodes"]}
    assert codes[one["id"]] == "c-main-02"
    routes = client.get(url(seeded, "export"), headers=sup).json()["normal_routes"]
    gate_to_lane_1n = next(r for r in routes if r["name"] == "Gate to lane 1 north")
    assert gate_to_lane_1n["nodes"] == ["c-gate-01", "c-main-02", "c-lane-1n"]


@pytest.mark.parametrize(
    ("change", "status", "code"),
    [
        (
            lambda b: b["links"].append(new_link(node_id("c-main-02"), node_id("c-main-01"))),
            409,
            "duplicate_link",
        ),
        (
            lambda b: b["links"].append(new_link(node_id("c-main-02"), node_id("c-main-02"))),
            422,
            "self_link",
        ),
        (
            lambda b: b["links"].append(new_link(node_id("c-main-02"), str(uuid4()))),
            422,
            "unknown_node",
        ),
        (lambda b: b["links"][0].update(travel_min_s=90, travel_max_s=60), 422, "travel_window"),
        (lambda b: b["nodes"][1].update(code=b["nodes"][0]["code"]), 409, "duplicate_code"),
        (lambda b: b["nodes"][0].update(zone_id=str(uuid4())), 422, "unknown_zone"),
    ],
)
def test_an_invalid_layout_is_refused_and_nothing_is_saved(
    client: TestClient,
    seeded: SeedReport,
    sup: Headers,
    change: Callable[[dict[str, Any]], None],
    status: int,
    code: str,
) -> None:
    before = client.get(url(seeded), headers=sup).json()
    body = editable(before)
    change(body)
    response = client.put(url(seeded), json=body, headers=sup)
    assert response.status_code == status
    error = response.json()
    assert error["code"] == code
    assert error["details"]["problems"][0]["code"] == code
    assert error["message"] == error["details"]["problems"][0]["message"]
    assert client.get(url(seeded), headers=sup).json() == before


def test_the_duplicate_message_names_the_link(
    client: TestClient, seeded: SeedReport, sup: Headers
) -> None:
    body = editable(client.get(url(seeded), headers=sup).json())
    body["links"].append(new_link(node_id("c-main-02"), node_id("c-main-01")))
    error = client.put(url(seeded), json=body, headers=sup).json()
    assert error["message"] == "link c-main-02 -> c-main-01 duplicates another link"


def test_zero_walking_time_is_malformed(
    client: TestClient, seeded: SeedReport, sup: Headers
) -> None:
    body = editable(client.get(url(seeded), headers=sup).json())
    body["links"][0]["travel_min_s"] = 0
    response = client.put(url(seeded), json=body, headers=sup)
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_a_guard_cannot_edit(client: TestClient, seeded: SeedReport, guard: Headers) -> None:
    body = editable(client.get(url(seeded), headers=guard).json())
    for response in (
        client.put(url(seeded), json=body, headers=guard),
        client.get(url(seeded, "export"), headers=guard),
        client.post("/api/v1/nodes", json={}, headers=guard),
        client.delete(f"/api/v1/links/{uuid4()}", headers=guard),
    ):
        assert response.status_code == 403
        assert response.json() == {
            "code": "forbidden",
            "message": "Only supervisor users can do this",
            "details": None,
        }


def camera(code: str, **fields: Any) -> dict[str, Any]:
    return {"code": code, "kind": "camera", "name": code, "x": 100, "y": 100, **fields}


def test_add_change_and_delete_a_node(client: TestClient, seeded: SeedReport, sup: Headers) -> None:
    created = client.post("/api/v1/nodes", json=camera("c-new-01"), headers=sup)
    assert created.status_code == 201
    node = created.json()
    assert node["status"] == "online" and node["zone_id"] is None

    zone = str(seed_id("taman-simulasi", "zone", "z-main"))
    patched = client.patch(
        f"/api/v1/nodes/{node['id']}", json={"heading_deg": 270, "zone_id": zone}, headers=sup
    )
    assert patched.status_code == 200
    assert (patched.json()["heading_deg"], patched.json()["zone_id"]) == (270, zone)
    assert patched.json()["code"] == "c-new-01"

    cleared = client.patch(f"/api/v1/nodes/{node['id']}", json={"zone_id": None}, headers=sup)
    assert cleared.json()["zone_id"] is None

    link = client.post(
        "/api/v1/links", json=new_link(node_id("c-main-04"), node["id"]), headers=sup
    )
    assert link.status_code == 201
    assert client.delete(f"/api/v1/nodes/{node['id']}", headers=sup).status_code == 204
    layout = client.get(url(seeded), headers=sup).json()
    assert node["id"] not in {n["id"] for n in layout["nodes"]}
    assert link.json()["id"] not in {item["id"] for item in layout["links"]}


def test_a_duplicate_node_code_is_a_conflict(
    client: TestClient, seeded: SeedReport, sup: Headers
) -> None:
    response = client.post("/api/v1/nodes", json=camera("c-main-01"), headers=sup)
    assert response.status_code == 409
    assert response.json()["code"] == "duplicate_code"
    renamed = client.patch(
        f"/api/v1/nodes/{node_id('c-main-02')}", json={"code": "c-main-01"}, headers=sup
    )
    assert renamed.status_code == 409


def test_renaming_a_node_renames_it_in_normal_routes(
    client: TestClient, seeded: SeedReport, sup: Headers
) -> None:
    response = client.patch(
        f"/api/v1/nodes/{node_id('c-lane-1n')}", json={"code": "c-lane-1-north"}, headers=sup
    )
    assert response.status_code == 200
    routes = client.get(url(seeded, "export"), headers=sup).json()["normal_routes"]
    assert routes[0] == {
        "name": "Gate to lane 1 north",
        "nodes": ["c-gate-01", "c-main-01", "c-lane-1-north"],
    }


def test_single_link_rules_follow_d65(client: TestClient, seeded: SeedReport, sup: Headers) -> None:
    def post(start: str, end: str, **fields: Any) -> Any:
        body = new_link(node_id(start), node_id(end), **fields)
        return client.post("/api/v1/links", json=body, headers=sup)

    assert post("c-main-02", "c-main-01").json()["code"] == "duplicate_link"  # reverse, two-way
    assert post("c-lane-1n", "c-lane-1n").json()["code"] == "self_link"
    # c-gate-01 -> c-main-01 is one-way, so the opposite one-way link is allowed ...
    back = post("c-main-01", "c-gate-01", bidirectional=False)
    assert back.status_code == 201
    # ... until either of them becomes two-way.
    response = client.patch(
        f"/api/v1/links/{back.json()['id']}", json={"bidirectional": True}, headers=sup
    )
    assert response.status_code == 409
    assert response.json()["code"] == "duplicate_link"

    window = client.patch(
        f"/api/v1/links/{back.json()['id']}", json={"travel_min_s": 99}, headers=sup
    )
    assert window.status_code == 422
    assert window.json()["code"] == "travel_window"
    assert client.delete(f"/api/v1/links/{back.json()['id']}", headers=sup).status_code == 204


def test_a_node_of_another_community_is_not_found(
    client: TestClient, seeded: SeedReport, sup: Headers
) -> None:
    response = client.patch(f"/api/v1/nodes/{uuid4()}", json={"name": "x"}, headers=sup)
    assert response.status_code == 404
    assert response.json()["code"] == "node_not_found"
