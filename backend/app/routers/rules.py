from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import current_user, require_role
from app.db import rule_store
from app.db.models import AppUser
from app.db.session import get_db
from app.engine.rules import RuleKey
from app.schemas.common import error_responses
from app.schemas.rules import RuleOut, RuleUpdate

router = APIRouter(tags=["rules"])

Db = Annotated[Session, Depends(get_db)]
User = Annotated[AppUser, Depends(current_user)]
# Thresholds are a supervisor screen (D-66); guards may read them.
Supervisor = Annotated[AppUser, Depends(require_role("supervisor"))]


@router.get("/rules", responses=error_responses(401))
def get_rules(user: User, db: Db) -> list[RuleOut]:
    """The community's three anomaly rules (F4), each with its thresholds and the rule-based
    severity of its alerts (D-60)."""
    return rule_store.list_rules(db, user.community_id)


@router.put("/rules/{key}", responses=error_responses(401, 403, 422))
def put_rule(key: RuleKey, body: RuleUpdate, user: Supervisor, db: Db) -> RuleOut:
    """Change a rule's thresholds, or switch it on or off; the next batch of events runs on them
    with no code change (F4). Fields left out stay as they are. 422 when the thresholds are not
    valid, with each problem in `details`."""
    rule = rule_store.update_rule(db, user.community_id, key, body)
    db.commit()
    return rule
