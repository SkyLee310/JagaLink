"""Layout editing (F1): community code and normal routes, link walking distance.

community.code is the slug a layout file carries (D-75); normal_routes feeds the off-route rule
and next-camera scoring (D-53); link.distance_m is part of the next-camera basis (D-20).

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("community", sa.Column("code", sa.Text(), nullable=True))
    # Existing communities get a slug from their name, e.g. "Taman Simulasi" -> taman-simulasi.
    op.execute(
        "UPDATE community SET code = "
        "trim(both '-' from lower(regexp_replace(name, '[^A-Za-z0-9]+', '-', 'g')))"
    )
    op.alter_column("community", "code", nullable=False)
    op.create_unique_constraint(op.f("uq_community_code"), "community", ["code"])
    op.add_column(
        "community",
        sa.Column(
            "normal_routes",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column("link", sa.Column("distance_m", sa.Double(), nullable=True))
    op.create_check_constraint(
        op.f("ck_link_distance_m"), "link", "distance_m IS NULL OR distance_m > 0"
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_link_distance_m"), "link", type_="check")
    op.drop_column("link", "distance_m")
    op.drop_column("community", "normal_routes")
    op.drop_constraint(op.f("uq_community_code"), "community", type_="unique")
    op.drop_column("community", "code")
