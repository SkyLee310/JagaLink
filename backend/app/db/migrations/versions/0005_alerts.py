"""Alerts (F4–F6): rule_config, anomaly, alert and alert_action (TECH_SPEC section 4).

An anomaly is one rule matching one track, with the events it relied on; it outlives its track,
whose ID is cleared when the track expires (D-56). Each anomaly has one alert, and each alert the
guards' confirm and dismiss actions.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RULE_KEYS = "rule_key IN ('after_hours', 'loiter', 'off_route')"


def _id() -> sa.Column:
    return sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False)


def _fk(table: str, column: str, target: str, ondelete: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column],
        [f"{target}.id"],
        name=op.f(f"fk_{table}_{column}_{target}"),
        ondelete=ondelete,
    )


def upgrade() -> None:
    op.create_table(
        "rule_config",
        _id(),
        sa.Column("community_id", sa.Uuid(), nullable=False),
        sa.Column("rule_key", sa.Text(), nullable=False),
        sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.CheckConstraint(RULE_KEYS, name=op.f("ck_rule_config_rule_key")),
        _fk("rule_config", "community_id", "community", "CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rule_config")),
        sa.UniqueConstraint(
            "community_id", "rule_key", name=op.f("uq_rule_config_community_id_rule_key")
        ),
    )
    op.create_table(
        "anomaly",
        _id(),
        sa.Column("community_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("track_id", sa.Uuid(), nullable=True),
        sa.Column("track_number", sa.Integer(), nullable=False),
        sa.Column("rule_key", sa.Text(), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("node_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_event_ids", postgresql.ARRAY(sa.Uuid()), nullable=False),
        sa.Column("score", sa.Double(), nullable=True),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.CheckConstraint(RULE_KEYS, name=op.f("ck_anomaly_rule_key")),
        _fk("anomaly", "community_id", "community", "CASCADE"),
        _fk("anomaly", "run_id", "scenario_run", "CASCADE"),
        _fk("anomaly", "track_id", "track", "SET NULL"),
        _fk("anomaly", "node_id", "node", "CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_anomaly")),
        sa.UniqueConstraint(
            "run_id",
            "track_number",
            "rule_key",
            name=op.f("uq_anomaly_run_id_track_number_rule_key"),
        ),
    )
    op.create_table(
        "alert",
        _id(),
        sa.Column("community_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("anomaly_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("severity_reason", sa.Text(), nullable=False),
        sa.Column("triage_status", sa.Text(), server_default="pending", nullable=False),
        sa.Column("assigned_user_id", sa.Uuid(), nullable=True),
        sa.Column("walk_s", sa.Double(), nullable=True),
        sa.Column("next_node_id", sa.Uuid(), nullable=True),
        sa.Column("next_node_basis", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acked_ts", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('new', 'acked', 'dismissed', 'escalated')", name=op.f("ck_alert_status")
        ),
        sa.CheckConstraint("severity IN ('high', 'medium', 'low')", name=op.f("ck_alert_severity")),
        sa.CheckConstraint(
            "triage_status IN ('pending', 'agent', 'fallback')",
            name=op.f("ck_alert_triage_status"),
        ),
        _fk("alert", "community_id", "community", "CASCADE"),
        _fk("alert", "run_id", "scenario_run", "CASCADE"),
        _fk("alert", "anomaly_id", "anomaly", "CASCADE"),
        _fk("alert", "assigned_user_id", "app_user", "SET NULL"),
        _fk("alert", "next_node_id", "node", "SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_alert")),
        sa.UniqueConstraint("anomaly_id", name=op.f("uq_alert_anomaly_id")),
    )
    op.create_index("ix_alert_run_id_created_ts", "alert", ["run_id", "created_ts"])
    op.create_table(
        "alert_action",
        _id(),
        sa.Column("alert_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), server_default="", nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("action IN ('confirm', 'dismiss')", name=op.f("ck_alert_action_action")),
        _fk("alert_action", "alert_id", "alert", "CASCADE"),
        _fk("alert_action", "user_id", "app_user", "CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_alert_action")),
    )


def downgrade() -> None:
    op.drop_table("alert_action")
    op.drop_index("ix_alert_run_id_created_ts", table_name="alert")
    op.drop_table("alert")
    op.drop_table("anomaly")
    op.drop_table("rule_config")
