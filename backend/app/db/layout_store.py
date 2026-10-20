"""Reads and writes a community's layout (F1): the editor's save, single edits, export, import.

Every write is checked by the pure rules in app.engine.layout first, so the API answers 409 or
422 with the D-40 body before anything touches the database. The caller commits.
"""

import uuid
from collections.abc import Sequence
from dataclasses import asdict
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.db.models import Community, Link, Node, Zone
from app.engine.layout import LinkSpec, NodeSpec, Problem, check_layout, status_for
from app.schemas.layout import (
    CommunityOut,
    LayoutFile,
    LayoutFileCommunity,
    LayoutFileLink,
    LayoutFileNode,
    LayoutFileZone,
    LayoutIn,
    LayoutOut,
    LinkIn,
    LinkOut,
    LinkPatch,
    NodeCreate,
    NodeIn,
    NodeOut,
    NodePatch,
    NormalRoute,
    ZoneOut,
)


def _zones(db: Session, community_id: uuid.UUID) -> list[Zone]:
    return list(
        db.scalars(select(Zone).where(Zone.community_id == community_id).order_by(Zone.code))
    )


def _nodes(db: Session, community_id: uuid.UUID) -> list[Node]:
    return list(
        db.scalars(select(Node).where(Node.community_id == community_id).order_by(Node.code))
    )


def _links(db: Session, community_id: uuid.UUID) -> list[Link]:
    query = select(Link).where(Link.community_id == community_id)
    return list(db.scalars(query.order_by(Link.from_node_id, Link.to_node_id)))


def _node_spec(node: Node | NodeCreate | NodeIn) -> NodeSpec:
    return NodeSpec(node.id, node.code, node.zone_id)


def _link_spec(link: Link | LinkIn) -> LinkSpec:
    return LinkSpec(
        link.from_node_id, link.to_node_id, link.travel_min_s, link.travel_max_s, link.bidirectional
    )


def _reject(problems: Sequence[Problem]) -> None:
    """Raise the D-40 error for these problems: 409 when all are duplicates, else 422."""
    if not problems:
        return
    first, more = problems[0], len(problems) - 1
    message = first.message + (f" (and {more} more)" if more else "")
    details = {"problems": [asdict(problem) for problem in problems]}
    raise ApiError(status_for(problems), first.code, message, details)


def _renamed_routes(routes: list[dict[str, Any]], renames: dict[str, str]) -> list[dict[str, Any]]:
    """Normal routes name nodes by code (D-53), so a renamed node is renamed in them too."""
    if not renames:
        return routes
    return [{**route, "nodes": [renames.get(c, c) for c in route["nodes"]]} for route in routes]


def load_layout(db: Session, community: Community) -> LayoutOut:
    return LayoutOut(
        community=CommunityOut.model_validate(community),
        zones=[ZoneOut.model_validate(zone) for zone in _zones(db, community.id)],
        nodes=[NodeOut.model_validate(node) for node in _nodes(db, community.id)],
        links=[LinkOut.model_validate(link) for link in _links(db, community.id)],
    )


def save_layout(db: Session, community: Community, body: LayoutIn) -> None:
    """Replace the community's nodes and links with the body's, in the caller's transaction.

    Nodes keep their IDs, so events and users that point at a node still do after a save.
    """
    existing = {node.id: node for node in _nodes(db, community.id)}
    new_ids = [node.id for node in body.nodes if node.id not in existing]
    taken = set(db.scalars(select(Node.id).where(Node.id.in_(new_ids)))) if new_ids else set()
    problems = [
        Problem("duplicate_node", f"node {node.code} uses an ID that belongs elsewhere")
        for node in body.nodes
        if node.id in taken
    ]
    problems += check_layout(
        [_node_spec(node) for node in body.nodes],
        [_link_spec(link) for link in body.links],
        [zone.id for zone in _zones(db, community.id)],
    )
    _reject(problems)

    renames = {
        existing[node.id].code: node.code
        for node in body.nodes
        if node.id in existing and existing[node.id].code != node.code
    }
    db.execute(delete(Link).where(Link.community_id == community.id))
    kept = {node.id for node in body.nodes}
    for node in existing.values():
        if node.id not in kept:
            db.delete(node)
    # Codes are unique per community: park renamed nodes on a free code first, so two nodes
    # can swap codes in one save.
    for node in body.nodes:
        if node.id in existing and existing[node.id].code in renames:
            existing[node.id].code = f"~{node.id}"
    db.flush()

    for item in body.nodes:
        node = existing.get(item.id) or Node(id=item.id, community_id=community.id)
        node.code, node.kind, node.name = item.code, item.kind, item.name
        node.x, node.y, node.heading_deg = item.x, item.y, item.heading_deg
        node.status, node.zone_id = item.status, item.zone_id
        db.add(node)
    db.flush()
    db.add_all(
        Link(
            id=item.id or uuid.uuid4(),
            community_id=community.id,
            from_node_id=item.from_node_id,
            to_node_id=item.to_node_id,
            travel_min_s=item.travel_min_s,
            travel_max_s=item.travel_max_s,
            bidirectional=item.bidirectional,
            distance_m=item.distance_m,
        )
        for item in body.links
    )
    community.normal_routes = _renamed_routes(community.normal_routes, renames)
    db.flush()


def create_node(db: Session, community: Community, body: NodeCreate) -> Node:
    node_id = body.id or uuid.uuid4()
    if db.get(Node, node_id) is not None:
        raise ApiError(409, "duplicate_node", "A node with this ID already exists")
    candidate = body.model_copy(update={"id": node_id})
    nodes = _nodes(db, community.id)
    _reject(
        check_layout(
            [*map(_node_spec, nodes), _node_spec(candidate)],
            [],
            [zone.id for zone in _zones(db, community.id)],
        )
    )
    node = Node(community_id=community.id, **candidate.model_dump())
    db.add(node)
    db.flush()
    return node


def update_node(db: Session, community: Community, node: Node, patch: NodePatch) -> Node:
    changes = {
        field: value
        for field, value in patch.model_dump(exclude_unset=True).items()
        if value is not None or field == "zone_id"
    }
    others = [other for other in _nodes(db, community.id) if other.id != node.id]
    proposed = NodeSpec(
        node.id, changes.get("code", node.code), changes.get("zone_id", node.zone_id)
    )
    _reject(
        check_layout(
            [*map(_node_spec, others), proposed], [], [zone.id for zone in _zones(db, community.id)]
        )
    )
    if changes.get("code", node.code) != node.code:
        community.normal_routes = _renamed_routes(
            community.normal_routes, {node.code: changes["code"]}
        )
    for field, value in changes.items():
        setattr(node, field, value)
    db.flush()
    return node


def create_link(db: Session, community: Community, body: LinkIn) -> Link:
    if body.id is not None and db.get(Link, body.id) is not None:
        raise ApiError(409, "duplicate_link", "A link with this ID already exists")
    _reject(
        check_layout(
            [_node_spec(node) for node in _nodes(db, community.id)],
            [*map(_link_spec, _links(db, community.id)), _link_spec(body)],
            [],
        )
    )
    link = Link(community_id=community.id, **body.model_dump(exclude={"id"}))
    link.id = body.id or uuid.uuid4()
    db.add(link)
    db.flush()
    return link


def update_link(db: Session, community: Community, link: Link, patch: LinkPatch) -> Link:
    changes = {
        field: value
        for field, value in patch.model_dump(exclude_unset=True).items()
        if value is not None or field == "distance_m"
    }
    proposed = LinkSpec(
        link.from_node_id,
        link.to_node_id,
        changes.get("travel_min_s", link.travel_min_s),
        changes.get("travel_max_s", link.travel_max_s),
        changes.get("bidirectional", link.bidirectional),
    )
    others = [other for other in _links(db, community.id) if other.id != link.id]
    _reject(
        check_layout(
            [_node_spec(node) for node in _nodes(db, community.id)],
            [*map(_link_spec, others), proposed],
            [],
        )
    )
    for field, value in changes.items():
        setattr(link, field, value)
    db.flush()
    return link


def export_layout(db: Session, community: Community) -> LayoutFile:
    """The layout as a file, in a canonical order, so export -> import -> export is identical."""
    zones = _zones(db, community.id)
    nodes = _nodes(db, community.id)
    zone_codes = {zone.id: zone.code for zone in zones}
    node_codes = {node.id: node.code for node in nodes}
    links = sorted(
        _links(db, community.id),
        key=lambda link: (node_codes[link.from_node_id], node_codes[link.to_node_id]),
    )
    return LayoutFile(
        community=LayoutFileCommunity(
            slug=community.code,
            name=community.name,
            map_image_url=community.map_image_url,
            scale_m_per_px=community.scale_m_per_px,
            timezone=community.timezone,
        ),
        zones=[
            LayoutFileZone(
                code=zone.code,
                name=zone.name,
                kind=zone.kind,
                polygon=[(x, y) for x, y in zone.polygon],
            )
            for zone in zones
        ],
        nodes=[
            LayoutFileNode(
                code=node.code,
                kind=node.kind,
                name=node.name,
                x=node.x,
                y=node.y,
                heading_deg=node.heading_deg,
                status=node.status,
                zone=zone_codes.get(node.zone_id) if node.zone_id else None,
            )
            for node in nodes
        ],
        links=[
            LayoutFileLink(
                from_node=node_codes[link.from_node_id],
                to_node=node_codes[link.to_node_id],
                travel_min_s=link.travel_min_s,
                travel_max_s=link.travel_max_s,
                bidirectional=link.bidirectional,
                distance_m=link.distance_m,
            )
            for link in links
        ],
        normal_routes=[NormalRoute.model_validate(route) for route in community.normal_routes],
    )


def import_layout(db: Session, community: Community, file: LayoutFile) -> None:
    """Replace the layout with the file's. Zones and nodes are matched by code and keep their IDs.

    The community keeps its own code: the file's slug only names where the file came from.
    """
    info = file.community
    community.name, community.map_image_url = info.name, info.map_image_url
    community.scale_m_per_px, community.timezone = info.scale_m_per_px, info.timezone
    community.normal_routes = [route.model_dump() for route in file.normal_routes]

    zones = {zone.code: zone for zone in _zones(db, community.id)}
    for item in file.zones:
        zone = zones.pop(item.code, None) or Zone(
            id=uuid.uuid4(), community_id=community.id, code=item.code
        )
        zone.name, zone.kind, zone.polygon = item.name, item.kind, [list(p) for p in item.polygon]
        db.add(zone)
    for leftover in zones.values():
        db.delete(leftover)
    db.flush()
    zone_ids = {zone.code: zone.id for zone in _zones(db, community.id)}

    db.execute(delete(Link).where(Link.community_id == community.id))
    nodes = {node.code: node for node in _nodes(db, community.id)}
    for item in file.nodes:
        node = nodes.pop(item.code, None) or Node(
            id=uuid.uuid4(), community_id=community.id, code=item.code
        )
        node.kind, node.name, node.x, node.y = item.kind, item.name, item.x, item.y
        node.heading_deg, node.status = item.heading_deg, item.status
        node.zone_id = zone_ids[item.zone] if item.zone else None
        db.add(node)
    for leftover in nodes.values():
        db.delete(leftover)
    db.flush()
    node_ids = {node.code: node.id for node in _nodes(db, community.id)}

    db.add_all(
        Link(
            id=uuid.uuid4(),
            community_id=community.id,
            from_node_id=node_ids[item.from_node],
            to_node_id=node_ids[item.to_node],
            travel_min_s=item.travel_min_s,
            travel_max_s=item.travel_max_s,
            bidirectional=item.bidirectional,
            distance_m=item.distance_m,
        )
        for item in file.links
    )
    db.flush()
