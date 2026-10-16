"""Layout and users: community, zone, node, link and app_user (TECH_SPEC section 4, D-75).

Revision ID: 0001
Revises:
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
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
        "community",
        _id(),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("map_image_url", sa.Text(), nullable=True),
        sa.Column("scale_m_per_px", sa.Double(), nullable=False),
        sa.Column("timezone", sa.Text(), server_default="Asia/Kuala_Lumpur", nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_community")),
    )
    op.create_table(
        "zone",
        _id(),
        *_community("zone"),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("polygon", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint("kind IN ('street', 'gate', 'lane')", name=op.f("ck_zone_kind")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_zone")),
        sa.UniqueConstraint("community_id", "code", name=op.f("uq_zone_community_id_code")),
    )
    op.create_table(
        "node",
        _id(),
        *_community("node"),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("x", sa.Double(), nullable=False),
        sa.Column("y", sa.Double(), nullable=False),
        sa.Column("heading_deg", sa.Double(), server_default=sa.text("0"), nullable=False),
        sa.Column("status", sa.Text(), server_default="online", nullable=False),
        sa.Column("zone_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint("kind IN ('camera', 'sensor')", name=op.f("ck_node_kind")),
        sa.CheckConstraint("status IN ('online', 'offline')", name=op.f("ck_node_status")),
        sa.CheckConstraint(
            "heading_deg >= 0 AND heading_deg < 360", name=op.f("ck_node_heading_deg")
        ),
        sa.ForeignKeyConstraint(
            ["zone_id"], ["zone.id"], name=op.f("fk_node_zone_id_zone"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_node")),
        sa.UniqueConstraint("community_id", "code", name=op.f("uq_node_community_id_code")),
    )
    op.create_table(
        "link",
        _id(),
        *_community("link"),
        sa.Column("from_node_id", sa.Uuid(), nullable=False),
        sa.Column("to_node_id", sa.Uuid(), nullable=False),
        sa.Column("travel_min_s", sa.Integer(), nullable=False),
        sa.Column("travel_max_s", sa.Integer(), nullable=False),
        sa.Column("bidirectional", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.CheckConstraint("from_node_id <> to_node_id", name=op.f("ck_link_not_self")),
        sa.CheckConstraint(
            "travel_min_s > 0 AND travel_min_s <= travel_max_s",
            name=op.f("ck_link_travel_window"),
        ),
        sa.ForeignKeyConstraint(
            ["from_node_id"],
            ["node.id"],
            name=op.f("fk_link_from_node_id_node"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["to_node_id"], ["node.id"], name=op.f("fk_link_to_node_id_node"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_link")),
        sa.UniqueConstraint(
            "from_node_id", "to_node_id", name=op.f("uq_link_from_node_id_to_node_id")
        ),
    )
    op.create_table(
        "app_user",
        _id(),
        *_community("app_user"),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("on_duty", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("current_node_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint("role IN ('guard', 'supervisor')", name=op.f("ck_app_user_role")),
        sa.ForeignKeyConstraint(
            ["current_node_id"],
            ["node.id"],
            name=op.f("fk_app_user_current_node_id_node"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_app_user")),
        sa.UniqueConstraint("community_id", "code", name=op.f("uq_app_user_community_id_code")),
    )


def downgrade() -> None:
    for table in ("app_user", "link", "node", "zone", "community"):
        op.drop_table(table)
