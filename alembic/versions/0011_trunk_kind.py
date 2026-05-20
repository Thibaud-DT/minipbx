"""trunk kind

Revision ID: 0011_trunk_kind
Revises: 0010_trunk_inbound_match
Create Date: 2026-05-20 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0011_trunk_kind"
down_revision = "0010_trunk_inbound_match"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("sip_trunks")}
    if "kind" not in columns:
        op.add_column("sip_trunks", sa.Column("kind", sa.String(length=30), nullable=False, server_default="sip_provider"))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("sip_trunks")}
    if "kind" in columns:
        op.drop_column("sip_trunks", "kind")
