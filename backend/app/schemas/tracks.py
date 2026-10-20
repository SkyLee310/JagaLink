from uuid import UUID

from pydantic import BaseModel

from app.engine.events import ObjectClass
from app.engine.linker import TrackStatus
from app.schemas.common import ApiDatetime


class SegmentOut(BaseModel):
    """A track's stay in front of one node, with the events it is built from."""

    node_id: UUID
    enter_ts: ApiDatetime
    exit_ts: ApiDatetime | None
    event_ids: list[UUID]


class TrackOut(BaseModel):
    """One anonymous cross-camera path (F3), its segments in order. `status` is `expired` only
    in the stream message that removes it: an expired track is deleted (D-11, D-56)."""

    id: UUID
    run_id: UUID
    anon_id: str
    object_class: ObjectClass
    status: TrackStatus
    first_ts: ApiDatetime
    last_ts: ApiDatetime
    expires_at: ApiDatetime
    segments: list[SegmentOut]
