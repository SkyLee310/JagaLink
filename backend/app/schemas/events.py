"""The event contract on the wire (D-16, D-30): what `POST /events` takes and `GET /events` returns.

The simulator, the video detector and the eval runner all send this one shape. An event says when
and where an object of a class was seen, under a per-camera ID; nothing in it may identify a
person (D-10).
"""

from typing import Annotated, Any
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
)

from app.engine.events import EventSource, EventType, ObjectClass
from app.schemas.common import ApiDatetime

# Words that would make an attribute about the person rather than the sighting (D-10).
IDENTITY_WORDS = frozenset(
    {"face", "name", "plate", "ic", "nric", "passport", "phone", "email", "address", "photo"}
)

AttrKey = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,31}$")]
AttrValue = Annotated[str, StringConstraints(max_length=64)] | int | float | bool | None
LocalTrackId = Annotated[
    str, StringConstraints(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._:#-]+$")
]


class EventIn(BaseModel):
    """One sighting. `local_track_id` is the camera's own anonymous ID for the object."""

    model_config = ConfigDict(extra="forbid")

    run_id: UUID
    ts: AwareDatetime
    node_id: UUID
    type: EventType
    object_class: ObjectClass
    local_track_id: LocalTrackId
    attrs: dict[AttrKey, AttrValue] = Field(default_factory=dict, max_length=10)
    source: EventSource

    @field_validator("attrs")
    @classmethod
    def no_identity(cls, attrs: dict[str, Any]) -> dict[str, Any]:
        named = sorted(key for key in attrs if IDENTITY_WORDS & set(key.split("_")))
        if named:
            raise ValueError(f"attrs describe the sighting, never the person: {', '.join(named)}")
        return attrs


class EventBatch(BaseModel):
    """Events of one run in time order; a batch is stored whole or not at all."""

    model_config = ConfigDict(extra="forbid")

    events: list[EventIn] = Field(min_length=1, max_length=1000)


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    seq: int
    ts: ApiDatetime
    node_id: UUID
    type: EventType
    object_class: ObjectClass
    local_track_id: str
    attrs: dict[str, Any]
    source: EventSource
