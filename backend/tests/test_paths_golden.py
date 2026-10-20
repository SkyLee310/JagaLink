"""M3.2: each scenario's night links into the same paths on every run (golden path files)."""

import pytest

from app.engine.graph import Graph
from app.engine.linker import Track
from app.sim.golden import (
    owners,
    paths_path,
    render_paths,
    script_tracks,
    seeded_graph,
    seeded_scripts,
)
from app.sim.script import Script

CODES = ["s1-evening-vehicle", "s2-night-fence"]


@pytest.fixture(scope="module")
def graph() -> Graph:
    return seeded_graph()


@pytest.fixture(scope="module")
def scripts() -> dict[str, Script]:
    return seeded_scripts()


@pytest.fixture(scope="module")
def tracks(scripts: dict[str, Script], graph: Graph) -> dict[str, list[Track]]:
    return {code: script_tracks(script, graph) for code, script in scripts.items()}


@pytest.mark.parametrize("code", CODES)
def test_linked_paths_match_the_golden_file(
    scripts: dict[str, Script], graph: Graph, code: str
) -> None:
    assert render_paths(scripts[code], graph) == paths_path(code).read_text(encoding="utf-8"), (
        f"{code} paths changed; if intended, run `uv run python -m app.sim.golden`"
    )


@pytest.mark.parametrize("code", CODES)
def test_every_track_follows_one_object_and_every_object_one_track(
    scripts: dict[str, Script], tracks: dict[str, list[Track]], code: str
) -> None:
    owner = owners(scripts[code])
    objects_per_track = [{owner[e] for e in track.event_ids()} for track in tracks[code]]
    assert all(len(objects) == 1 for objects in objects_per_track)
    keys = [next(iter(objects)) for objects in objects_per_track]
    assert len(keys) == len(set(keys)) == len(scripts[code].objects)


@pytest.mark.parametrize("code", CODES)
def test_each_target_is_one_path_through_all_its_visits(
    scripts: dict[str, Script], tracks: dict[str, list[Track]], code: str
) -> None:
    owner = owners(scripts[code])
    for target in (obj for obj in scripts[code].objects if obj.is_target):
        [track] = [t for t in tracks[code] if {owner[e] for e in t.event_ids()} == {target.key}]
        assert track.nodes() == [stop.node for stop in target.stops]
        assert track.status == "closed"
