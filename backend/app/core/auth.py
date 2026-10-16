"""Session tokens (D-76): HMAC-SHA256 over a small JSON payload, standard library only.

A token is base64url(payload) + "." + base64url(signature). The payload holds the user ID
(sub), role, community ID (cid) and the expiry (exp, Unix seconds). There is no session
table: a token stays valid until it expires or SESSION_SECRET changes.
"""

import base64
import hashlib
import hmac
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.settings import Settings, get_settings
from app.db.models import AppUser
from app.db.session import get_db

TOKEN_TTL = timedelta(hours=12)

bearer = HTTPBearer(auto_error=False, description="The token from POST /api/v1/session")


@dataclass(frozen=True)
class Claims:
    user_id: UUID
    role: str
    community_id: UUID
    expires_at: datetime


def _encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _signature(payload: str, secret: str) -> str:
    return _encode(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest())


def issue_token(user: AppUser, now: datetime, secret: str) -> tuple[str, datetime]:
    expires_at = (now + TOKEN_TTL).replace(microsecond=0)
    claims = {
        "sub": str(user.id),
        "role": user.role,
        "cid": str(user.community_id),
        "exp": int(expires_at.timestamp()),
    }
    payload = _encode(json.dumps(claims, separators=(",", ":")).encode())
    return f"{payload}.{_signature(payload, secret)}", expires_at


def verify_token(token: str, now: datetime, secret: str) -> Claims:
    invalid = ApiError(401, "invalid_token", "The session token is not valid; pick a role again")
    payload, _, signature = token.partition(".")
    expected = _signature(payload, secret)
    if not payload or not hmac.compare_digest(signature.encode(), expected.encode()):
        raise invalid
    try:
        data = json.loads(_decode(payload))
        claims = Claims(
            user_id=UUID(data["sub"]),
            role=data["role"],
            community_id=UUID(data["cid"]),
            expires_at=datetime.fromtimestamp(data["exp"], UTC),
        )
    except (ValueError, KeyError, TypeError, AttributeError, OverflowError, OSError):
        raise invalid from None
    if now >= claims.expires_at:
        raise ApiError(401, "token_expired", "The session has expired; pick a role again")
    return claims


def current_claims(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Claims:
    if credentials is None:
        raise ApiError(401, "unauthorized", "Send the session token as a bearer token")
    return verify_token(credentials.credentials, datetime.now(UTC), settings.session_secret)


def current_user(
    claims: Annotated[Claims, Depends(current_claims)],
    db: Annotated[Session, Depends(get_db)],
) -> AppUser:
    user = db.get(AppUser, claims.user_id)
    if user is None:
        raise ApiError(401, "invalid_token", "The session user no longer exists; pick a role again")
    return user


def require_role(*roles: str) -> Callable[[AppUser], AppUser]:
    """Dependency that lets only these roles through; role checks run on the server (D-41)."""

    def check(user: Annotated[AppUser, Depends(current_user)]) -> AppUser:
        if user.role not in roles:
            raise ApiError(403, "forbidden", f"Only {' or '.join(roles)} users can do this")
        return user

    return check
