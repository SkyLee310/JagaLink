"""M4.2: rule thresholds read and change through the API, with no code change (F4)."""

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

Headers = Callable[[str], dict[str, str]]

DEFAULTS = [
    {
        "key": "after_hours",
        "name": "After-hours entry",
        "enabled": True,
        "params": {
            "start": "23:00:00",
            "end": "06:00:00",
            "zone_kinds": ["lane"],
            "severity": "medium",
        },
    },
    {
        "key": "loiter",
        "name": "Loitering",
        "enabled": True,
        "params": {"threshold_s": 180.0, "window_s": 600.0, "severity": "medium"},
    },
    {
        "key": "off_route",
        "name": "Off-route movement",
        "enabled": True,
        "params": {"severity": "high"},
    },
]


def put(client: TestClient, headers: dict[str, str], key: str, body: dict[str, Any]) -> Any:
    return client.put(f"/api/v1/rules/{key}", json=body, headers=headers)


def test_every_user_reads_the_seeded_rules(client: TestClient, headers_for: Headers) -> None:
    response = client.get("/api/v1/rules", headers=headers_for("u-guard-01"))
    assert response.status_code == 200
    assert response.json() == DEFAULTS
    assert client.get("/api/v1/rules").status_code == 401


def test_a_supervisor_changes_one_threshold_and_the_rest_stay(
    client: TestClient, headers_for: Headers
) -> None:
    sup = headers_for("u-sup-01")
    response = put(client, sup, "loiter", {"params": {"threshold_s": 60}})
    assert response.status_code == 200
    assert response.json()["params"] == {
        "threshold_s": 60.0,
        "window_s": 600.0,
        "severity": "medium",
    }
    off = put(client, sup, "after_hours", {"enabled": False, "params": {"start": "22:30"}})
    assert (off.json()["enabled"], off.json()["params"]["start"]) == (False, "22:30:00")

    rules = {rule["key"]: rule for rule in client.get("/api/v1/rules", headers=sup).json()}
    assert rules["loiter"]["params"]["threshold_s"] == 60.0
    assert rules["after_hours"]["enabled"] is False
    assert rules["off_route"] == DEFAULTS[2]


def test_guards_cannot_change_rules(client: TestClient, headers_for: Headers) -> None:
    response = put(client, headers_for("u-guard-01"), "loiter", {"params": {"threshold_s": 60}})
    assert (response.status_code, response.json()["code"]) == (403, "forbidden")


@pytest.mark.parametrize(
    ("key", "body", "code"),
    [
        ("loiter", {"params": {"threshold_s": 900}}, "invalid_rule"),  # longer than the window
        ("loiter", {"params": {"threshold_s": 0}}, "invalid_rule"),
        ("loiter", {"params": {"radius_m": 5}}, "invalid_rule"),
        ("after_hours", {"params": {"zone_kinds": []}}, "invalid_rule"),
        ("after_hours", {"params": {"zone_kinds": ["roof"]}}, "invalid_rule"),
        ("off_route", {"params": {"severity": "urgent"}}, "invalid_rule"),
        ("speeding", {"enabled": False}, "validation_error"),
        ("loiter", {"enabled": False, "colour": "red"}, "validation_error"),
    ],
)
def test_invalid_thresholds_are_refused_and_nothing_changes(
    client: TestClient, headers_for: Headers, key: str, body: dict[str, Any], code: str
) -> None:
    sup = headers_for("u-sup-01")
    response = put(client, sup, key, body)
    assert (response.status_code, response.json()["code"]) == (422, code)
    assert response.json()["details"]
    assert client.get("/api/v1/rules", headers=sup).json() == DEFAULTS
