from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import current_user
from app.core.errors import ApiError
from app.db.models import AppUser, Community, Link, Node, Zone
from app.db.session import get_db
from app.schemas.common import error_responses
from app.schemas.layout import CommunityOut, LayoutOut, LinkOut, NodeOut, ZoneOut

router = APIRouter(prefix="/communities", tags=["layout"])


@router.get("/{community_id}/layout", responses=error_responses(401, 403, 404, 422))
def get_layout(
    community_id: UUID,
    user: Annotated[AppUser, Depends(current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> LayoutOut:
    """Zones, nodes and links of one community in a single response (F1)."""
    community = db.get(Community, community_id)
    if community is None:
        raise ApiError(404, "community_not_found", "No community has that ID")
    if user.community_id != community.id:
        raise ApiError(403, "forbidden", "Your session belongs to another community")

    zones = db.scalars(select(Zone).where(Zone.community_id == community_id).order_by(Zone.code))
    nodes = db.scalars(select(Node).where(Node.community_id == community_id).order_by(Node.code))
    links = db.scalars(
        select(Link)
        .where(Link.community_id == community_id)
        .order_by(Link.from_node_id, Link.to_node_id)
    )
    return LayoutOut(
        community=CommunityOut.model_validate(community),
        zones=[ZoneOut.model_validate(zone) for zone in zones],
        nodes=[NodeOut.model_validate(node) for node in nodes],
        links=[LinkOut.model_validate(link) for link in links],
    )
