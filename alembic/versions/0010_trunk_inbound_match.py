"""trunk inbound match

Revision ID: 0010_trunk_inbound_match
Revises: 0009_remove_contacts
Create Date: 2026-05-11 10:10:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0010_trunk_inbound_match"
down_revision = "0009_remove_contacts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("sip_trunks")}
    if "inbound_match" not in columns:
        op.add_column("sip_trunks", sa.Column("inbound_match", sa.String(length=500), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("sip_trunks")}
    if "inbound_match" in columns:
        op.drop_column("sip_trunks", "inbound_match")
