"""outbound rules

Revision ID: 0003_outbound_rules
Revises: 0002_ring_groups_inbound_routes
Create Date: 2026-05-09 00:00:02.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_outbound_rules"
down_revision = "0002_ring_groups_inbound_routes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "outbound_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("prefix", sa.String(length=8), nullable=True),
        sa.Column("allow_national", sa.Boolean(), nullable=False),
        sa.Column("allow_mobile", sa.Boolean(), nullable=False),
        sa.Column("allow_international", sa.Boolean(), nullable=False),
        sa.Column("emergency_numbers", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("outbound_rules")
