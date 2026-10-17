from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import issue_token
from app.core.errors import ApiError
from app.core.settings import Settings, get_settings
from app.db.models import AppUser
from app.db.session import get_db
from app.schemas.common import error_responses
from app.schemas.session import SessionIn, SessionOut, SessionUserOut

router = APIRouter(prefix="/session", tags=["session"])


@router.get("/users")
def list_session_users(db: Annotated[Session, Depends(get_db)]) -> list[SessionUserOut]:
    """Seeded users for the role picker. No token: there is no real login (D-28)."""
    users = db.scalars(select(AppUser).order_by(AppUser.role, AppUser.code))
    return [SessionUserOut.model_validate(user) for user in users]


@router.post("", responses=error_responses(404, 422))
def create_session(
    body: SessionIn,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SessionOut:
    """Pick a seeded user. Send the token back as `Authorization: Bearer <token>` (D-41)."""
    user = db.get(AppUser, body.user_id)
    if user is None:
        raise ApiError(404, "user_not_found", "No seeded user has that ID")
    token, expires_at = issue_token(user, datetime.now(UTC), settings.session_secret)
    return SessionOut(
        token=token,
        expires_at=expires_at,
        user=SessionUserOut.model_validate(user),
        community_id=user.community_id,
    )
