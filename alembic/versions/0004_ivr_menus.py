"""ivr menus

Revision ID: 0004_ivr_menus
Revises: 0003_outbound_rules
Create Date: 2026-05-10 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_ivr_menus"
down_revision = "0003_outbound_rules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ivr_menus",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("number", sa.String(length=6), nullable=False),
        sa.Column("prompt_mode", sa.String(length=20), nullable=False),
        sa.Column("prompt_text", sa.Text(), nullable=True),
        sa.Column("prompt_audio_path", sa.String(length=500), nullable=True),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("fallback_type", sa.String(length=40), nullable=False),
        sa.Column("fallback_target", sa.String(length=80), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_ivr_menus_number", "ivr_menus", ["number"], unique=True)
    op.create_table(
        "ivr_options",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("menu_id", sa.Integer(), sa.ForeignKey("ivr_menus.id", ondelete="CASCADE"), nullable=False),
        sa.Column("digit", sa.String(length=1), nullable=False),
        sa.Column("destination_type", sa.String(length=40), nullable=False),
        sa.Column("destination_target", sa.String(length=80), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("ivr_options")
    op.drop_index("ix_ivr_menus_number", table_name="ivr_menus")
    op.drop_table("ivr_menus")
