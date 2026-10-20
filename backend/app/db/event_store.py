"""Stores and reads events (F2): the ingest every source shares (D-30), and the event filters.

The caller commits. Ingest checks the batch against its run before anything is written, so a bad
batch answers with the D-40 body and stores nothing.
"""

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.db.models import Event, Node, ScenarioRun
from app.schemas.events import EventIn, EventOut

OPEN_STATES = ("ready", "playing", "paused")


def ingest(db: Session, run: ScenarioRun, events: Sequence[EventIn]) -> list[Event]:
    """Store a batch of one run's events after the run's latest, in time order."""
    if run.state not in OPEN_STATES:
        raise ApiError(409, "run_closed", f"The run is {run.state}; it takes no more events")
    others = sorted({str(event.run_id) for event in events if event.run_id != run.id})
    if others:
        raise ApiError(422, "mixed_runs", "Every event in a batch must name the same run", others)
    nodes = set(db.scalars(select(Node.id).where(Node.community_id == run.community_id)))
    unknown = sorted({str(event.node_id) for event in events if event.node_id not in nodes})
    if unknown:
        message = "Some events name a node outside the community"
        raise ApiError(422, "unknown_node", message, unknown)

    # Lock the run, so concurrent batches for it queue up instead of racing for seq numbers.
    db.refresh(run, with_for_update=True)
    last = db.execute(
        select(Event.seq, Event.ts).where(Event.run_id == run.id).order_by(Event.seq.desc())
    ).first()
    seq, previous = (last.seq, last.ts) if last else (0, None)
    stored: list[Event] = []
    for index, event in enumerate(events):
        if previous is not None and event.ts < previous:
            raise ApiError(
                422,
                "out_of_order",
                "Events must arrive in time order, after the run's latest event",
                {"index": index, "ts": event.ts, "after": previous},
            )
        previous = event.ts
        seq += 1
        stored.append(
            Event(
                id=uuid.uuid4(),
                community_id=run.community_id,
                run_id=run.id,
                seq=seq,
                ts=event.ts,
                node_id=event.node_id,
                type=event.type,
                object_class=event.object_class,
                local_track_id=event.local_track_id,
                attrs=event.attrs,
                source=event.source,
            )
        )
    db.add_all(stored)
    db.flush()
    return stored


def find_events(
    db: Session,
    community_id: uuid.UUID,
    run_id: uuid.UUID | None = None,
    node_id: uuid.UUID | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 500,
) -> list[Event]:
    """Events in time order; `start` is inclusive and `end` exclusive."""
    query = select(Event).where(Event.community_id == community_id)
    if run_id is not None:
        query = query.where(Event.run_id == run_id)
    if node_id is not None:
        query = query.where(Event.node_id == node_id)
    if start is not None:
        query = query.where(Event.ts >= start)
    if end is not None:
        query = query.where(Event.ts < end)
    return list(db.scalars(query.order_by(Event.ts, Event.seq).limit(limit)))


def event_count(db: Session, run_id: uuid.UUID) -> int:
    last = db.scalar(select(Event.seq).where(Event.run_id == run_id).order_by(Event.seq.desc()))
    return last or 0


def event_message(event: Event) -> tuple[str, dict[str, object]]:
    """The `event` message the stream pushes for a stored event (D-36)."""
    return "event", EventOut.model_validate(event).model_dump(mode="json")
