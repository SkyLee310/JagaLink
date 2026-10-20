from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import AwareDatetime
from sqlalchemy.orm import Session

from app.core.auth import current_user, require_role
from app.db import event_store
from app.db.models import AppUser
from app.db.session import get_db
from app.routers.scenarios import Runs, own_run
from app.schemas.common import error_responses
from app.schemas.events import EventBatch, EventOut

router = APIRouter(tags=["events"])

Db = Annotated[Session, Depends(get_db)]


@router.post("/events", status_code=201, responses=error_responses(401, 403, 404, 409, 422))
def post_events(
    body: EventBatch,
    user: Annotated[AppUser, Depends(require_role("supervisor"))],
    db: Db,
    runs: Runs,
) -> list[EventOut]:
    """Store a batch of one run's events in the one contract (D-16, D-30), link them into
    tracks (F3) and push both.

    422 for a malformed event, an unknown field, a node outside the community, mixed runs, or
    an event earlier than the run's latest; 409 once the run has finished or been replaced.
    """
    run = own_run(db, user, body.events[0].run_id)
    items = runs.ingest(db, run, body.events)
    runs.hub.publish_threadsafe(run.id, items)
    return [EventOut.model_validate(data) for kind, data in items if kind == "event"]


@router.get("/events", responses=error_responses(401, 422))
def get_events(
    user: Annotated[AppUser, Depends(current_user)],
    db: Db,
    run_id: UUID | None = None,
    node_id: UUID | None = None,
    start: Annotated[AwareDatetime | None, Query(alias="from")] = None,
    end: Annotated[AwareDatetime | None, Query(alias="to")] = None,
    limit: Annotated[int, Query(ge=1, le=5000)] = 500,
) -> list[EventOut]:
    """Events in time order, filtered by run, node and time (`from` inclusive, `to` not)."""
    found = event_store.find_events(db, user.community_id, run_id, node_id, start, end, limit)
    return [EventOut.model_validate(event) for event in found]
