from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import current_user
from app.core.errors import ApiError
from app.db import track_store
from app.db.models import AppUser
from app.db.session import get_db
from app.engine.linker import TrackStatus
from app.schemas.common import error_responses
from app.schemas.tracks import TrackOut

router = APIRouter(tags=["tracks"])

Db = Annotated[Session, Depends(get_db)]
User = Annotated[AppUser, Depends(current_user)]


@router.get("/tracks", responses=error_responses(401, 422))
def get_tracks(
    user: User,
    db: Db,
    run_id: UUID | None = None,
    status: TrackStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=5000)] = 500,
) -> list[TrackOut]:
    """Anonymous paths (F3) in order of their first sighting, each with its ordered segments."""
    return track_store.find_tracks(db, user.community_id, run_id, status, limit)


@router.get("/tracks/{track_id}", responses=error_responses(401, 404, 422))
def get_track(track_id: UUID, user: User, db: Db) -> TrackOut:
    """One path with its ordered segments; 404 once it has expired and been purged (D-11)."""
    track = track_store.get_track(db, user.community_id, track_id)
    if track is None:
        raise ApiError(404, "track_not_found", "No track in your community has that ID")
    return track
