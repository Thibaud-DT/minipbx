"""ring groups and inbound routes

Revision ID: 0002_ring_groups_inbound_routes
Revises: 0001_initial
Create Date: 2026-05-09 00:00:01.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_ring_groups_inbound_routes"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ring_groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("number", sa.String(length=6), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("fallback_type", sa.String(length=40), nullable=False),
        sa.Column("fallback_target", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_ring_groups_number", "ring_groups", ["number"], unique=True)
    op.create_table(
        "ring_group_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ring_group_id", sa.Integer(), sa.ForeignKey("ring_groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("extension_id", sa.Integer(), sa.ForeignKey("extensions.id", ondelete="CASCADE"), nullable=False),
    )
    op.create_table(
        "inbound_routes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("did_number", sa.String(length=40), nullable=True),
        sa.Column("use_business_hours", sa.Boolean(), nullable=False),
        sa.Column("open_destination_type", sa.String(length=40), nullable=False),
        sa.Column("open_destination_target", sa.String(length=80), nullable=True),
        sa.Column("closed_destination_type", sa.String(length=40), nullable=False),
        sa.Column("closed_destination_target", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("inbound_routes")
    op.drop_table("ring_group_members")
    op.drop_index("ix_ring_groups_number", table_name="ring_groups")
    op.drop_table("ring_groups")
