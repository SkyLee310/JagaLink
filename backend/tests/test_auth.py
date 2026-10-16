import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.core.auth import issue_token, require_role, verify_token
from app.core.errors import ApiError
from app.db.models import AppUser

SECRET = "test-session-secret"
NOW = datetime(2026, 10, 17, 13, 14, 5, 250000, tzinfo=UTC)
SOME_ID = "6f1c2a7e-3d4b-4f8a-9c1e-2b7d5a9e4c30"


def make_user(role: str = "guard") -> AppUser:
    return AppUser(id=uuid4(), community_id=uuid4(), code="u-test-01", name="Test", role=role)


def b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def signed(payload: bytes) -> str:
    """A token over any payload, signed the way D-76 signs one."""
    text = b64(payload)
    return f"{text}.{b64(hmac.new(SECRET.encode(), text.encode(), hashlib.sha256).digest())}"


def rejection(token: str, now: datetime = NOW, secret: str = SECRET) -> str:
    with pytest.raises(ApiError) as caught:
        verify_token(token, now, secret)
    assert caught.value.status == 401
    return caught.value.code


def test_token_round_trip() -> None:
    user = make_user()
    token, expires_at = issue_token(user, NOW, SECRET)
    claims = verify_token(token, NOW, SECRET)
    assert (claims.user_id, claims.role, claims.community_id) == (
        user.id,
        "guard",
        user.community_id,
    )
    assert claims.expires_at == expires_at == datetime(2026, 10, 18, 1, 14, 5, tzinfo=UTC)


def test_token_expires_after_twelve_hours() -> None:
    token, expires_at = issue_token(make_user(), NOW, SECRET)
    verify_token(token, expires_at - timedelta(seconds=1), SECRET)
    assert rejection(token, now=expires_at) == "token_expired"


def test_changed_claims_break_the_signature() -> None:
    token, _ = issue_token(make_user("guard"), NOW, SECRET)
    payload, signature = token.split(".")
    claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    forged = b64(json.dumps({**claims, "role": "supervisor"}).encode())
    assert rejection(f"{forged}.{signature}") == "invalid_token"


def test_another_secret_is_rejected() -> None:
    token, _ = issue_token(make_user(), NOW, SECRET)
    assert rejection(token, secret="another-secret") == "invalid_token"


@pytest.mark.parametrize("token", ["", ".", "garbage", "abc.def", "a.b.c"])
def test_garbage_is_rejected(token: str) -> None:
    assert rejection(token) == "invalid_token"


@pytest.mark.parametrize(
    "claims",
    [
        "not json",
        "[]",
        '{"sub": 1}',
        '{"sub": "x", "role": "guard"}',
        f'{{"sub": "{SOME_ID}", "role": "guard", "cid": "{SOME_ID}", "exp": 1e20}}',
    ],
)
def test_signed_nonsense_is_rejected(claims: str) -> None:
    assert rejection(signed(claims.encode())) == "invalid_token"


def test_require_role() -> None:
    supervisors_only = require_role("supervisor")
    supervisor = make_user("supervisor")
    assert supervisors_only(supervisor) is supervisor
    with pytest.raises(ApiError) as caught:
        supervisors_only(make_user("guard"))
    assert (caught.value.status, caught.value.code) == (403, "forbidden")
