"""pbx settings

Revision ID: 0008_pbx_settings
Revises: 0007_contacts
Create Date: 2026-05-10 00:00:04.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0008_pbx_settings"
down_revision = "0007_contacts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pbx_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("network_mode", sa.String(length=20), nullable=False),
        sa.Column("sip_port", sa.Integer(), nullable=False),
        sa.Column("rtp_start", sa.Integer(), nullable=False),
        sa.Column("rtp_end", sa.Integer(), nullable=False),
        sa.Column("external_address", sa.String(length=120), nullable=False),
        sa.Column("local_net", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("pbx_settings")
