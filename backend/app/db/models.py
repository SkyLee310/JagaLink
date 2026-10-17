"""Tables from TECH_SPEC §4. Every change here needs an Alembic migration (D-38)."""

import uuid
from typing import Any, Literal, get_args

from sqlalchemy import Boolean, CheckConstraint, Double, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy import text as sql
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

ZoneKind = Literal["street", "gate", "lane"]
NodeKind = Literal["camera", "sensor"]
NodeStatus = Literal["online", "offline"]
Role = Literal["guard", "supervisor"]


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
    name: Mapped[str] = mapped_column(Text)
    map_image_url: Mapped[str | None] = mapped_column(Text)
    scale_m_per_px: Mapped[float] = mapped_column(Double)
    timezone: Mapped[str] = mapped_column(
        Text, default="Asia/Kuala_Lumpur", server_default="Asia/Kuala_Lumpur"
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
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    community_id: Mapped[uuid.UUID] = community_fk()
    from_node_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("node.id", ondelete="CASCADE"))
    to_node_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("node.id", ondelete="CASCADE"))
    travel_min_s: Mapped[int] = mapped_column(Integer)
    travel_max_s: Mapped[int] = mapped_column(Integer)
    bidirectional: Mapped[bool] = mapped_column(Boolean, default=True, server_default=sql("true"))


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
