"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-09 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users_admin",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=80), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_users_admin_username", "users_admin", ["username"], unique=True)
    op.create_table(
        "extensions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("number", sa.String(length=6), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("sip_username", sa.String(length=80), nullable=False),
        sa.Column("sip_secret", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("voicemail_enabled", sa.Boolean(), nullable=False),
        sa.Column("voicemail_pin", sa.String(length=12), nullable=False),
        sa.Column("outbound_enabled", sa.Boolean(), nullable=False),
        sa.Column("inbound_enabled", sa.Boolean(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_extensions_number", "extensions", ["number"], unique=True)
    op.create_index("ix_extensions_sip_username", "extensions", ["sip_username"], unique=True)
    op.create_table(
        "sip_trunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("host", sa.String(length=255), nullable=False),
        sa.Column("username", sa.String(length=120), nullable=False),
        sa.Column("password_secret", sa.String(length=255), nullable=False),
        sa.Column("from_user", sa.String(length=120), nullable=True),
        sa.Column("from_domain", sa.String(length=255), nullable=True),
        sa.Column("transport", sa.String(length=20), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "config_revisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("generated_path", sa.String(length=500), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("config_revisions")
    op.drop_table("sip_trunks")
    op.drop_index("ix_extensions_sip_username", table_name="extensions")
    op.drop_index("ix_extensions_number", table_name="extensions")
    op.drop_table("extensions")
    op.drop_index("ix_users_admin_username", table_name="users_admin")
    op.drop_table("users_admin")
