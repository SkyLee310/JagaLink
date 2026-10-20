"""Tracks (F3): track and track_segment (TECH_SPEC section 4).

A track is one anonymous cross-camera path; its segments, in `position` order, are its stays in
front of each node. Expired tracks are deleted with their segments (D-56).

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _id() -> sa.Column:
    return sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False)


def upgrade() -> None:
    op.create_table(
        "track",
        _id(),
        sa.Column("community_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("anon_id", sa.Text(), nullable=False),
        sa.Column("object_class", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("first_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "object_class IN ('person', 'vehicle')", name=op.f("ck_track_object_class")
        ),
        sa.CheckConstraint(
            "status IN ('active', 'closed', 'expired')", name=op.f("ck_track_status")
        ),
        sa.ForeignKeyConstraint(
            ["community_id"],
            ["community.id"],
            name=op.f("fk_track_community_id_community"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["scenario_run.id"],
            name=op.f("fk_track_run_id_scenario_run"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_track")),
        sa.UniqueConstraint("run_id", "number", name=op.f("uq_track_run_id_number")),
        sa.UniqueConstraint("run_id", "anon_id", name=op.f("uq_track_run_id_anon_id")),
    )
    op.create_index("ix_track_community_id_expires_at", "track", ["community_id", "expires_at"])
    op.create_table(
        "track_segment",
        _id(),
        sa.Column("track_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("node_id", sa.Uuid(), nullable=False),
        sa.Column("enter_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exit_ts", sa.DateTime(timezone=True), nullable=True),
        sa.Column("event_ids", postgresql.ARRAY(sa.Uuid()), nullable=False),
        sa.ForeignKeyConstraint(
            ["track_id"],
            ["track.id"],
            name=op.f("fk_track_segment_track_id_track"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["node_id"],
            ["node.id"],
            name=op.f("fk_track_segment_node_id_node"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_track_segment")),
        sa.UniqueConstraint(
            "track_id", "position", name=op.f("uq_track_segment_track_id_position")
        ),
    )


def downgrade() -> None:
    op.drop_table("track_segment")
    op.drop_index("ix_track_community_id_expires_at", table_name="track")
    op.drop_table("track")
