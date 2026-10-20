"""Load the seeded community (Taman Simulasi, D-69), its staff and its scenarios.

python -m app.db.seed            insert the community if it is missing; refresh its scenarios
python -m app.db.seed --reset    delete it and load it again (clean demo state, D-27)
"""

import argparse
import uuid
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.models import AppUser, Community, Link, Node, Role, Scenario, Zone
from app.db.session import get_engine
from app.schemas.common import Code
from app.schemas.layout import LayoutFile
from app.sim.scenario import SCENARIO_DIR, NightClock, load_scenario, scenario_paths

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DEFAULT_LAYOUT = DATA_DIR / "layouts" / "taman-simulasi.json"
DEFAULT_USERS = DATA_DIR / "seed" / "users.json"

# Seeded rows get IDs derived from their codes, so every database holds the same IDs.
SEED_NAMESPACE = uuid.UUID("6f1c2a7e-3d4b-4f8a-9c1e-2b7d5a9e4c30")


def seed_id(community_slug: str, kind: str, code: str = "") -> uuid.UUID:
    return uuid.uuid5(SEED_NAMESPACE, f"{community_slug}/{kind}/{code}")


class SeedUser(BaseModel):
    code: Code
    name: str
    role: Role
    on_duty: bool = False
    current_node: Code | None = None


class UsersFile(BaseModel):
    community: Code
    users: list[SeedUser]


@dataclass(frozen=True)
class SeedReport:
    community_id: uuid.UUID
    created: bool
    zones: int
    nodes: int
    links: int
    users: int
    scenarios: int


def seed(
    db: Session,
    layout_path: Path = DEFAULT_LAYOUT,
    users_path: Path = DEFAULT_USERS,
    reset: bool = False,
    scenario_dir: Path = SCENARIO_DIR,
) -> SeedReport:
    """Insert the community unless it exists; with reset, replace it. The caller commits.

    Scenarios always follow their files, so a database seeded before a scenario existed gets it.
    """
    layout = LayoutFile.model_validate_json(layout_path.read_text(encoding="utf-8"))
    staff = UsersFile.model_validate_json(users_path.read_text(encoding="utf-8"))
    slug = layout.community.slug
    if staff.community != slug:
        raise ValueError(f"{users_path.name} is for {staff.community}, not {slug}")
    unknown = [u.code for u in staff.users if u.current_node not in (None, *layout.node_codes)]
    if unknown:
        raise ValueError(f"users at unknown nodes: {', '.join(unknown)}")

    community_id = seed_id(slug, "community")
    if db.scalar(select(Community.id).where(Community.id == community_id)) is not None:
        if not reset:
            seed_scenarios(db, community_id, layout, scenario_dir)
            return _report(db, community_id, created=False)
        db.execute(delete(Community).where(Community.id == community_id))  # cascades
        db.expunge_all()

    zone_ids = {zone.code: seed_id(slug, "zone", zone.code) for zone in layout.zones}
    node_ids = {node.code: seed_id(slug, "node", node.code) for node in layout.nodes}
    community = layout.community
    db.add(
        Community(
            id=community_id,
            code=slug,
            name=community.name,
            map_image_url=community.map_image_url,
            scale_m_per_px=community.scale_m_per_px,
            timezone=community.timezone,
            normal_routes=[route.model_dump() for route in layout.normal_routes],
        )
    )
    db.flush()
    db.add_all(
        Zone(
            id=zone_ids[zone.code],
            community_id=community_id,
            code=zone.code,
            name=zone.name,
            kind=zone.kind,
            polygon=[list(point) for point in zone.polygon],
        )
        for zone in layout.zones
    )
    db.flush()
    db.add_all(
        Node(
            id=node_ids[node.code],
            community_id=community_id,
            code=node.code,
            kind=node.kind,
            name=node.name,
            x=node.x,
            y=node.y,
            heading_deg=node.heading_deg,
            status=node.status,
            zone_id=zone_ids[node.zone] if node.zone else None,
        )
        for node in layout.nodes
    )
    db.flush()
    db.add_all(
        Link(
            id=seed_id(slug, "link", f"{link.from_node}>{link.to_node}"),
            community_id=community_id,
            from_node_id=node_ids[link.from_node],
            to_node_id=node_ids[link.to_node],
            travel_min_s=link.travel_min_s,
            travel_max_s=link.travel_max_s,
            bidirectional=link.bidirectional,
            distance_m=link.distance_m,
        )
        for link in layout.links
    )
    db.add_all(
        AppUser(
            id=seed_id(slug, "user", user.code),
            community_id=community_id,
            code=user.code,
            name=user.name,
            role=user.role,
            on_duty=user.on_duty,
            current_node_id=node_ids[user.current_node] if user.current_node else None,
        )
        for user in staff.users
    )
    db.flush()
    seed_scenarios(db, community_id, layout, scenario_dir)
    return _report(db, community_id, created=True)


def seed_scenarios(
    db: Session, community_id: uuid.UUID, layout: LayoutFile, directory: Path = SCENARIO_DIR
) -> None:
    """Insert or update one row per scenario file of this community; the truth stays in the file."""
    slug = layout.community.slug
    for path in scenario_paths(directory):
        scenario = load_scenario(path)
        if scenario.community != slug:
            continue
        clock = NightClock(scenario.night, layout.community.timezone)
        window = clock.at(scenario.live_window.end) - clock.at(scenario.live_window.start)
        row = db.get(Scenario, seed_id(slug, "scenario", scenario.code))
        if row is None:
            row = Scenario(id=seed_id(slug, "scenario", scenario.code), community_id=community_id)
            db.add(row)
        row.code = scenario.code
        row.name = scenario.name
        row.description = scenario.description
        row.script_path = path.name
        row.duration_s = round(window.total_seconds())
    db.flush()


def _report(db: Session, community_id: uuid.UUID, created: bool) -> SeedReport:
    def count(model: type[Zone | Node | Link | AppUser | Scenario]) -> int:
        query = select(func.count()).select_from(model).where(model.community_id == community_id)
        return db.scalar(query) or 0

    return SeedReport(
        community_id,
        created,
        count(Zone),
        count(Node),
        count(Link),
        count(AppUser),
        count(Scenario),
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Load the seeded community and its staff.")
    parser.add_argument("--reset", action="store_true", help="delete the community, load it again")
    args = parser.parse_args(argv)
    with Session(get_engine()) as db:
        report = seed(db, reset=args.reset)
        db.commit()
    state = "loaded" if report.created else "already present, left unchanged"
    print(
        f"Seed {state}: {report.zones} zones, {report.nodes} nodes, "
        f"{report.links} links, {report.users} users, {report.scenarios} scenarios"
    )


if __name__ == "__main__":
    main()
