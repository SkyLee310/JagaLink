from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.auth import current_user, require_role
from app.core.errors import ApiError
from app.db import layout_store
from app.db.models import AppUser, Community, Link, Node
from app.db.session import get_db
from app.schemas.common import error_responses
from app.schemas.layout import (
    LayoutFile,
    LayoutIn,
    LayoutOut,
    LinkIn,
    LinkOut,
    LinkPatch,
    NodeCreate,
    NodeOut,
    NodePatch,
)

router = APIRouter(tags=["layout"])

Db = Annotated[Session, Depends(get_db)]
# The layout editor, import and export are supervisor screens (D-66).
Supervisor = Annotated[AppUser, Depends(require_role("supervisor"))]


def _community(community_id: UUID, user: AppUser, db: Session) -> Community:
    community = db.get(Community, community_id)
    if community is None:
        raise ApiError(404, "community_not_found", "No community has that ID")
    if user.community_id != community.id:
        raise ApiError(403, "forbidden", "Your session belongs to another community")
    return community


def own_community(
    community_id: UUID, user: Annotated[AppUser, Depends(current_user)], db: Db
) -> Community:
    return _community(community_id, user, db)


def edited_community(community_id: UUID, user: Supervisor, db: Db) -> Community:
    return _community(community_id, user, db)


def _own_node(node_id: UUID, user: AppUser, db: Session) -> Node:
    node = db.get(Node, node_id)
    if node is None or node.community_id != user.community_id:
        raise ApiError(404, "node_not_found", "No node in your community has that ID")
    return node


def _own_link(link_id: UUID, user: AppUser, db: Session) -> Link:
    link = db.get(Link, link_id)
    if link is None or link.community_id != user.community_id:
        raise ApiError(404, "link_not_found", "No link in your community has that ID")
    return link


@router.get("/communities/{community_id}/layout", responses=error_responses(401, 403, 404, 422))
def get_layout(community: Annotated[Community, Depends(own_community)], db: Db) -> LayoutOut:
    """Zones, nodes and links of one community in a single response (F1)."""
    return layout_store.load_layout(db, community)


@router.put(
    "/communities/{community_id}/layout", responses=error_responses(401, 403, 404, 409, 422)
)
def save_layout(
    body: LayoutIn, community: Annotated[Community, Depends(edited_community)], db: Db
) -> LayoutOut:
    """Save the whole layout in one transaction (F1). Zones stay as seeded (D-64).

    A self-link, an unknown node or zone, or a bad walking-time window answers 422; a duplicate
    link (D-65) or node code answers 409. Nothing is saved unless the whole layout is valid.
    """
    layout_store.save_layout(db, community, body)
    db.commit()
    return layout_store.load_layout(db, community)


@router.get("/communities/{community_id}/export", responses=error_responses(401, 403, 404, 422))
def export_layout(
    response: Response, community: Annotated[Community, Depends(edited_community)], db: Db
) -> LayoutFile:
    """The layout as a file, with codes instead of IDs (D-75)."""
    response.headers["Content-Disposition"] = f'attachment; filename="{community.code}.json"'
    return layout_store.export_layout(db, community)


@router.post("/communities/{community_id}/import", responses=error_responses(401, 403, 404, 422))
def import_layout(
    body: LayoutFile, community: Annotated[Community, Depends(edited_community)], db: Db
) -> LayoutOut:
    """Replace the layout with a file's; zones and nodes with the same code keep their IDs."""
    layout_store.import_layout(db, community, body)
    db.commit()
    return layout_store.load_layout(db, community)


@router.post("/nodes", status_code=201, responses=error_responses(401, 403, 409, 422))
def create_node(body: NodeCreate, user: Supervisor, db: Db) -> NodeOut:
    """Add a camera or sensor to the supervisor's community."""
    node = layout_store.create_node(db, _community(user.community_id, user, db), body)
    db.commit()
    return NodeOut.model_validate(node)


@router.patch("/nodes/{node_id}", responses=error_responses(401, 403, 404, 409, 422))
def update_node(node_id: UUID, body: NodePatch, user: Supervisor, db: Db) -> NodeOut:
    """Change some of a node's fields; `status: offline` marks a blind spot (F9)."""
    node = _own_node(node_id, user, db)
    layout_store.update_node(db, _community(user.community_id, user, db), node, body)
    db.commit()
    return NodeOut.model_validate(node)


@router.delete("/nodes/{node_id}", status_code=204, responses=error_responses(401, 403, 404))
def delete_node(node_id: UUID, user: Supervisor, db: Db) -> None:
    """Delete a node and every link that touches it."""
    db.delete(_own_node(node_id, user, db))
    db.commit()


@router.post("/links", status_code=201, responses=error_responses(401, 403, 409, 422))
def create_link(body: LinkIn, user: Supervisor, db: Db) -> LinkOut:
    """Link two nodes of the supervisor's community with a walking-time window."""
    link = layout_store.create_link(db, _community(user.community_id, user, db), body)
    db.commit()
    return LinkOut.model_validate(link)


@router.patch("/links/{link_id}", responses=error_responses(401, 403, 404, 409, 422))
def update_link(link_id: UUID, body: LinkPatch, user: Supervisor, db: Db) -> LinkOut:
    """Change a link's walking times, direction or distance."""
    link = _own_link(link_id, user, db)
    layout_store.update_link(db, _community(user.community_id, user, db), link, body)
    db.commit()
    return LinkOut.model_validate(link)


@router.delete("/links/{link_id}", status_code=204, responses=error_responses(401, 403, 404))
def delete_link(link_id: UUID, user: Supervisor, db: Db) -> None:
    db.delete(_own_link(link_id, user, db))
    db.commit()
