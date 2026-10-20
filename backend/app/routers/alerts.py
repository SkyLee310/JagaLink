from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import current_user
from app.core.errors import ApiError
from app.db import alert_store
from app.db.models import AlertStatus, AppUser, Community, ScenarioRun
from app.db.session import get_db
from app.routers.scenarios import Runs
from app.schemas.alerts import AlertActionIn, AlertOut
from app.schemas.common import error_responses

router = APIRouter(tags=["alerts"])

Db = Annotated[Session, Depends(get_db)]
User = Annotated[AppUser, Depends(current_user)]


def not_found() -> ApiError:
    return ApiError(404, "alert_not_found", "No alert in your community has that ID")


@router.get("/alerts", responses=error_responses(401, 422))
def get_alerts(
    user: User,
    db: Db,
    run_id: UUID | None = None,
    status: AlertStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=5000)] = 500,
) -> list[AlertOut]:
    """Alerts (F4–F6) in the order they were raised, each with its rule, severity, guard, next
    camera and evidence."""
    return alert_store.find_alerts(db, user.community_id, run_id, status, limit)


@router.get("/alerts/{alert_id}", responses=error_responses(401, 404, 422))
def get_alert(alert_id: UUID, user: User, db: Db) -> AlertOut:
    alert = alert_store.get_alert(db, user.community_id, alert_id)
    if alert is None:
        raise not_found()
    return alert


@router.post("/alerts/{alert_id}/actions", responses=error_responses(401, 404, 409, 422))
def act_on_alert(alert_id: UUID, body: AlertActionIn, user: User, db: Db, runs: Runs) -> AlertOut:
    """Confirm or dismiss an alert with an optional one-line reason (F6). The action is stamped
    with the run's clock, so the incident timeline can place it (D-62), and every open screen
    gets the change as `alert_update`. 409 when the alert has been handled already."""
    found = alert_store.get_alert(db, user.community_id, alert_id)
    if found is None:
        raise not_found()
    run = db.get_one(ScenarioRun, found.run_id)
    clock = runs.clock(db, db.get_one(Community, user.community_id), run)
    alert = alert_store.lock(db, user.community_id, alert_id)
    if alert is None:
        raise not_found()
    if alert.status in alert_store.HANDLED:
        raise ApiError(
            409, "alert_already_handled", f"The alert was {alert.status} already", alert.status
        )
    out = alert_store.act(db, alert, user, body.action, body.reason, max(clock, alert.created_ts))
    db.commit()
    runs.hub.publish_threadsafe(run.id, [alert_store.alert_message("alert_update", out)])
    return out
