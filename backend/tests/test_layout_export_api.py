"""M1.3: a layout leaves as a file and comes back identical (F1)."""

import json
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.db.seed import DEFAULT_LAYOUT, SeedReport, seed_id
from app.schemas.layout import LayoutFile

Headers = dict[str, str]


@pytest.fixture
def sup(headers_for: Callable[[str], Headers]) -> Headers:
    return headers_for("u-sup-01")


def url(seeded: SeedReport, part: str) -> str:
    return f"/api/v1/communities/{seeded.community_id}/{part}"


def canonical(file: dict[str, Any]) -> dict[str, Any]:
    """A layout file in export order: zones and nodes by code, links by their two codes."""
    data = LayoutFile.model_validate(file).model_dump(mode="json")
    data["zones"].sort(key=lambda zone: zone["code"])
    data["nodes"].sort(key=lambda node: node["code"])
    data["links"].sort(key=lambda link: (link["from_node"], link["to_node"]))
    return data


def test_export_import_export_is_identical(
    client: TestClient, seeded: SeedReport, sup: Headers
) -> None:
    first = client.get(url(seeded, "export"), headers=sup)
    assert first.status_code == 200
    assert first.headers["content-disposition"] == 'attachment; filename="taman-simulasi.json"'
    imported = client.post(url(seeded, "import"), json=first.json(), headers=sup)
    assert imported.status_code == 200
    second = client.get(url(seeded, "export"), headers=sup)
    assert second.content == first.content


def test_the_seed_file_survives_the_database(
    client: TestClient, seeded: SeedReport, sup: Headers
) -> None:
    exported = client.get(url(seeded, "export"), headers=sup).json()
    seed_file = json.loads(DEFAULT_LAYOUT.read_text(encoding="utf-8"))
    assert exported == canonical(seed_file)


def test_import_keeps_ids_by_code_and_replaces_the_rest(
    client: TestClient, seeded: SeedReport, sup: Headers
) -> None:
    file = client.get(url(seeded, "export"), headers=sup).json()
    file["community"]["name"] = "Taman Simulasi Baru"
    moved = next(node for node in file["nodes"] if node["code"] == "c-main-02")
    moved["x"] += 40
    file["nodes"] = [node for node in file["nodes"] if node["code"] != "s-club-01"]
    file["links"] = [link for link in file["links"] if "s-club-01" not in link.values()]
    file["nodes"].append({**moved, "code": "c-main-05", "name": "Main road, new"})
    file["links"].append(
        {"from_node": "c-main-04", "to_node": "c-main-05", "travel_min_s": 5, "travel_max_s": 7}
    )

    layout = client.post(url(seeded, "import"), json=file, headers=sup).json()

    nodes = {node["code"]: node for node in layout["nodes"]}
    assert layout["community"]["name"] == "Taman Simulasi Baru"
    assert layout["community"]["code"] == "taman-simulasi"
    assert nodes["c-main-02"]["id"] == str(seed_id("taman-simulasi", "node", "c-main-02"))
    assert nodes["c-main-02"]["x"] == moved["x"]
    assert "s-club-01" not in nodes and "c-main-05" in nodes
    assert len(layout["links"]) == len(file["links"])


def test_a_broken_file_is_refused_and_nothing_changes(
    client: TestClient, seeded: SeedReport, sup: Headers
) -> None:
    before = client.get(url(seeded, "export"), headers=sup).json()
    broken = json.loads(json.dumps(before))
    broken["links"].append(dict(broken["links"][0]))  # the same link twice
    response = client.post(url(seeded, "import"), json=broken, headers=sup)
    assert response.status_code == 422
    assert "duplicates another link" in response.json()["details"][0]["msg"]
    assert client.get(url(seeded, "export"), headers=sup).json() == before
