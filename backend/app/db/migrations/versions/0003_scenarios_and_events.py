"""Scenarios, runs and events (F2): scenario, scenario_run and event (TECH_SPEC section 4).

The ground truth stays in the scenario files (D-70); a partial unique index keeps one live run
per community (D-77); event.seq is the ingest order the pipeline reads.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _id() -> sa.Column:
    return sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False)


def _community(table: str) -> list[sa.Column | sa.ForeignKeyConstraint]:
    return [
        sa.Column("community_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["community_id"],
            ["community.id"],
            name=op.f(f"fk_{table}_community_id_community"),
            ondelete="CASCADE",
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "scenario",
        _id(),
        *_community("scenario"),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("script_path", sa.Text(), nullable=False),
        sa.Column("duration_s", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scenario")),
        sa.UniqueConstraint("community_id", "code", name=op.f("uq_scenario_community_id_code")),
    )
    op.create_table(
        "scenario_run",
        _id(),
        *_community("scenario_run"),
        sa.Column("scenario_id", sa.Uuid(), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("speed", sa.Double(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("mode IN ('live', 'eval')", name=op.f("ck_scenario_run_mode")),
        sa.CheckConstraint(
            "state IN ('ready', 'playing', 'paused', 'finished', 'stopped')",
            name=op.f("ck_scenario_run_state"),
        ),
        sa.CheckConstraint("speed > 0", name=op.f("ck_scenario_run_speed")),
        sa.ForeignKeyConstraint(
            ["scenario_id"],
            ["scenario.id"],
            name=op.f("fk_scenario_run_scenario_id_scenario"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scenario_run")),
    )
    op.create_index(
        "uq_scenario_run_live",
        "scenario_run",
        ["community_id"],
        unique=True,
        postgresql_where=sa.text("mode = 'live' AND state <> 'stopped'"),
    )
    op.create_table(
        "event",
        _id(),
        *_community("event"),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("node_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("object_class", sa.Text(), nullable=False),
        sa.Column("local_track_id", sa.Text(), nullable=False),
        sa.Column(
            "attrs", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("source", sa.Text(), nullable=False),
        sa.CheckConstraint("type IN ('appear', 'dwell', 'disappear')", name=op.f("ck_event_type")),
        sa.CheckConstraint(
            "object_class IN ('person', 'vehicle')", name=op.f("ck_event_object_class")
        ),
        sa.CheckConstraint("source IN ('sim', 'video')", name=op.f("ck_event_source")),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["scenario_run.id"],
            name=op.f("fk_event_run_id_scenario_run"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["node_id"], ["node.id"], name=op.f("fk_event_node_id_node"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_event")),
        sa.UniqueConstraint("run_id", "seq", name=op.f("uq_event_run_id_seq")),
    )
    op.create_index("ix_event_run_id_ts", "event", ["run_id", "ts"])


def downgrade() -> None:
    op.drop_table("event")
    op.drop_index("uq_scenario_run_live", table_name="scenario_run")
    op.drop_table("scenario_run")
    op.drop_table("scenario")
