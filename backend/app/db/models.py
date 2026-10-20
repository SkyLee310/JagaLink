"""Tables from TECH_SPEC §4. Every change here needs an Alembic migration (D-38)."""

import uuid
from datetime import UTC, datetime
from typing import Any, Literal, get_args

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Double,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy import text as sql
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.engine.events import EventSource, EventType, ObjectClass
from app.engine.linker import TrackStatus

ZoneKind = Literal["street", "gate", "lane"]
NodeKind = Literal["camera", "sensor"]
NodeStatus = Literal["online", "offline"]
Role = Literal["guard", "supervisor"]
RunMode = Literal["live", "eval"]
RunState = Literal["ready", "playing", "paused", "finished", "stopped"]


def one_of(column: str, values: Any) -> str:
    """SQL for a CHECK that keeps a text column inside a Literal's values."""
    return f"{column} IN ({', '.join(repr(v) for v in get_args(values))})"


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=sql("gen_random_uuid()")
    )


def community_fk() -> Mapped[uuid.UUID]:
    return mapped_column(ForeignKey("community.id", ondelete="CASCADE"))


class Community(Base):
    __tablename__ = "community"

    id: Mapped[uuid.UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    map_image_url: Mapped[str | None] = mapped_column(Text)
    scale_m_per_px: Mapped[float] = mapped_column(Double)
    timezone: Mapped[str] = mapped_column(
        Text, default="Asia/Kuala_Lumpur", server_default="Asia/Kuala_Lumpur"
    )
    # Named node-code sequences: the off-route rule and next-camera scoring read them (D-53).
    normal_routes: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, server_default=sql("'[]'::jsonb")
    )


class Zone(Base):
    __tablename__ = "zone"
    __table_args__ = (
        UniqueConstraint("community_id", "code"),
        CheckConstraint(one_of("kind", ZoneKind), name="kind"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    community_id: Mapped[uuid.UUID] = community_fk()
    code: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    polygon: Mapped[list[list[float]]] = mapped_column(JSONB)


class Node(Base):
    __tablename__ = "node"
    __table_args__ = (
        UniqueConstraint("community_id", "code"),
        CheckConstraint(one_of("kind", NodeKind), name="kind"),
        CheckConstraint(one_of("status", NodeStatus), name="status"),
        CheckConstraint("heading_deg >= 0 AND heading_deg < 360", name="heading_deg"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    community_id: Mapped[uuid.UUID] = community_fk()
    code: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    x: Mapped[float] = mapped_column(Double)
    y: Mapped[float] = mapped_column(Double)
    heading_deg: Mapped[float] = mapped_column(Double, default=0, server_default=sql("0"))
    status: Mapped[str] = mapped_column(Text, default="online", server_default="online")
    zone_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("zone.id", ondelete="SET NULL"))


class Link(Base):
    __tablename__ = "link"
    __table_args__ = (
        UniqueConstraint("from_node_id", "to_node_id"),
        CheckConstraint("from_node_id <> to_node_id", name="not_self"),
        CheckConstraint("travel_min_s > 0 AND travel_min_s <= travel_max_s", name="travel_window"),
        CheckConstraint("distance_m IS NULL OR distance_m > 0", name="distance_m"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    community_id: Mapped[uuid.UUID] = community_fk()
    from_node_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("node.id", ondelete="CASCADE"))
    to_node_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("node.id", ondelete="CASCADE"))
    travel_min_s: Mapped[int] = mapped_column(Integer)
    travel_max_s: Mapped[int] = mapped_column(Integer)
    bidirectional: Mapped[bool] = mapped_column(Boolean, default=True, server_default=sql("true"))
    # Walking distance along the streets, part of the next-camera basis (D-20).
    distance_m: Mapped[float | None] = mapped_column(Double)


class AppUser(Base):
    __tablename__ = "app_user"
    __table_args__ = (
        UniqueConstraint("community_id", "code"),
        CheckConstraint(one_of("role", Role), name="role"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    community_id: Mapped[uuid.UUID] = community_fk()
    code: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    on_duty: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sql("false"))
    current_node_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("node.id", ondelete="SET NULL")
    )


class Scenario(Base):
    """A scripted scenario (F2). Its ground truth stays in the script file (D-70)."""

    __tablename__ = "scenario"
    __table_args__ = (UniqueConstraint("community_id", "code"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    community_id: Mapped[uuid.UUID] = community_fk()
    code: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    # File name under backend/data/scenarios/.
    script_path: Mapped[str] = mapped_column(Text)
    # Length of the live window the player plays (D-71).
    duration_s: Mapped[int] = mapped_column(Integer)


class ScenarioRun(Base):
    """One playback (live) or headless replay (eval) of a scenario."""

    __tablename__ = "scenario_run"
    __table_args__ = (
        CheckConstraint(one_of("mode", RunMode), name="mode"),
        CheckConstraint(one_of("state", RunState), name="state"),
        CheckConstraint("speed > 0", name="speed"),
        # D-77: a community has one live run at a time; starting another stops the old one.
        Index(
            "uq_scenario_run_live",
            "community_id",
            unique=True,
            postgresql_where=sql("mode = 'live' AND state <> 'stopped'"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    community_id: Mapped[uuid.UUID] = community_fk()
    scenario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scenario.id", ondelete="CASCADE"))
    mode: Mapped[str] = mapped_column(Text)
    speed: Mapped[float] = mapped_column(Double)
    state: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Event(Base):
    """One sighting event in the single contract every source posts (D-16, D-30)."""

    __tablename__ = "event"
    __table_args__ = (
        UniqueConstraint("run_id", "seq"),
        CheckConstraint(one_of("type", EventType), name="type"),
        CheckConstraint(one_of("object_class", ObjectClass), name="object_class"),
        CheckConstraint(one_of("source", EventSource), name="source"),
        Index("ix_event_run_id_ts", "run_id", "ts"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    community_id: Mapped[uuid.UUID] = community_fk()
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scenario_run.id", ondelete="CASCADE"))
    # Ingest order within the run: the pipeline and the feed read events in this order.
    seq: Mapped[int] = mapped_column(Integer)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    node_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("node.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(Text)
    object_class: Mapped[str] = mapped_column(Text)
    local_track_id: Mapped[str] = mapped_column(Text)
    # Never personal data (D-10); the ingest schema refuses identity-like keys.
    attrs: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=sql("'{}'::jsonb")
    )
    source: Mapped[str] = mapped_column(Text)


class Track(Base):
    """One anonymous cross-camera path (F3). It is deleted when it expires (D-11, D-56)."""

    __tablename__ = "track"
    __table_args__ = (
        UniqueConstraint("run_id", "number"),
        UniqueConstraint("run_id", "anon_id"),
        CheckConstraint(one_of("object_class", ObjectClass), name="object_class"),
        CheckConstraint(one_of("status", TrackStatus), name="status"),
        Index("ix_track_community_id_expires_at", "community_id", "expires_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    community_id: Mapped[uuid.UUID] = community_fk()
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scenario_run.id", ondelete="CASCADE"))
    # Order of creation within the run: the linker's track number.
    number: Mapped[int] = mapped_column(Integer)
    # Pseudonymous, per run; it says nothing about who the object is (D-09).
    anon_id: Mapped[str] = mapped_column(Text)
    object_class: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    first_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TrackSegment(Base):
    """A track's stay in front of one node; `position` orders a track's segments."""

    __tablename__ = "track_segment"
    __table_args__ = (UniqueConstraint("track_id", "position"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    track_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("track.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer)
    node_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("node.id", ondelete="CASCADE"))
    enter_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    exit_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    event_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(Uuid))
