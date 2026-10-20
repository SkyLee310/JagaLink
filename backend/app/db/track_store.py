"""Stores and reads tracks (F3). The caller commits.

Track IDs and anonymous IDs come from the run and the linker's track number, so rebuilding a
run's linker after a restart lands on the same rows.
"""

import uuid
from collections.abc import Iterable, Mapping
from datetime import datetime

from sqlalchemy import Select, delete, select
from sqlalchemy.orm import Session

from app.core.hub import Item
from app.db.models import Track, TrackSegment
from app.engine import linker
from app.schemas.tracks import SegmentOut, TrackOut

ANON_BITS = 24
ANON_STEP = 0x9E3779B1
"""Odd, so stepping by it is a bijection on 24 bits: anonymous IDs never repeat within a run."""


def track_id(run_id: uuid.UUID, number: int) -> uuid.UUID:
    return uuid.uuid5(run_id, f"track-{number}")


def anon_id(run_id: uuid.UUID, number: int) -> str:
    """A pseudonymous ID such as obj-3fa91c, unique within its run (D-11)."""
    mask = (1 << ANON_BITS) - 1
    return f"obj-{(number * ANON_STEP + (run_id.int & mask)) & mask:06x}"


def track_out(
    run_id: uuid.UUID, track: linker.Track, node_ids: Mapping[str, uuid.UUID]
) -> TrackOut:
    return TrackOut(
        id=track_id(run_id, track.number),
        run_id=run_id,
        anon_id=anon_id(run_id, track.number),
        object_class=track.object_class,
        status=track.status,
        first_ts=track.first_ts,
        last_ts=track.last_ts,
        expires_at=track.expires_at,
        segments=[
            SegmentOut(
                node_id=node_ids[segment.node],
                enter_ts=segment.enter,
                exit_ts=segment.exit,
                event_ids=[uuid.UUID(event_id) for event_id in segment.event_ids],
            )
            for segment in track.segments
        ],
    )


def save(db: Session, community_id: uuid.UUID, tracks: Iterable[tuple[int, TrackOut]]) -> None:
    """Write each (track number, track) and replace its segments."""
    for number, out in tracks:
        row = db.get(Track, out.id)
        if row is None:
            row = Track(
                id=out.id,
                community_id=community_id,
                run_id=out.run_id,
                number=number,
                anon_id=out.anon_id,
                object_class=out.object_class,
            )
            db.add(row)
        row.status = out.status
        row.first_ts, row.last_ts, row.expires_at = out.first_ts, out.last_ts, out.expires_at
        db.execute(delete(TrackSegment).where(TrackSegment.track_id == out.id))
        db.add_all(
            TrackSegment(
                id=uuid.uuid4(),
                track_id=out.id,
                position=position,
                node_id=segment.node_id,
                enter_ts=segment.enter_ts,
                exit_ts=segment.exit_ts,
                event_ids=segment.event_ids,
            )
            for position, segment in enumerate(out.segments)
        )
    db.flush()


def remove(db: Session, ids: Iterable[uuid.UUID]) -> None:
    """Delete tracks and their segments."""
    ids = list(ids)
    if ids:
        db.execute(delete(Track).where(Track.id.in_(ids)))


def purge_expired(db: Session, community_id: uuid.UUID, now: datetime) -> list[uuid.UUID]:
    """The purge job (D-11, D-56): delete every track of the community that expired by `now`,
    in event time (D-31). Returns the deleted IDs."""
    deleted = db.scalars(
        delete(Track)
        .where(Track.community_id == community_id, Track.expires_at <= now)
        .returning(Track.id)
    )
    return list(deleted)


def load(db: Session, query: Select[tuple[Track]]) -> list[TrackOut]:
    """Tracks with their segments in order."""
    rows = list(db.scalars(query))
    segments: dict[uuid.UUID, list[TrackSegment]] = {row.id: [] for row in rows}
    if rows:
        for segment in db.scalars(
            select(TrackSegment)
            .where(TrackSegment.track_id.in_(segments))
            .order_by(TrackSegment.track_id, TrackSegment.position)
        ):
            segments[segment.track_id].append(segment)
    return [
        TrackOut(
            id=row.id,
            run_id=row.run_id,
            anon_id=row.anon_id,
            object_class=row.object_class,
            status=row.status,
            first_ts=row.first_ts,
            last_ts=row.last_ts,
            expires_at=row.expires_at,
            segments=[
                SegmentOut(
                    node_id=segment.node_id,
                    enter_ts=segment.enter_ts,
                    exit_ts=segment.exit_ts,
                    event_ids=segment.event_ids,
                )
                for segment in segments[row.id]
            ],
        )
        for row in rows
    ]


def find_tracks(
    db: Session,
    community_id: uuid.UUID,
    run_id: uuid.UUID | None = None,
    status: linker.TrackStatus | None = None,
    limit: int = 500,
) -> list[TrackOut]:
    query = select(Track).where(Track.community_id == community_id)
    if run_id is not None:
        query = query.where(Track.run_id == run_id)
    if status is not None:
        query = query.where(Track.status == status)
    return load(db, query.order_by(Track.first_ts, Track.number).limit(limit))


def run_tracks(db: Session, run_id: uuid.UUID) -> list[TrackOut]:
    return load(db, select(Track).where(Track.run_id == run_id).order_by(Track.number))


def get_track(db: Session, community_id: uuid.UUID, track: uuid.UUID) -> TrackOut | None:
    found = load(db, select(Track).where(Track.id == track, Track.community_id == community_id))
    return found[0] if found else None


def track_message(track: TrackOut) -> Item:
    """The `track_update` message the stream pushes for a new, changed or expired track (D-36)."""
    return "track_update", track.model_dump(mode="json")
