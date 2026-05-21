"""trunk fxo stage method

Revision ID: 0012_trunk_fxo_stage_method
Revises: 0011_trunk_kind
Create Date: 2026-05-21 12:30:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0012_trunk_fxo_stage_method"
down_revision = "0011_trunk_kind"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("sip_trunks")}
    if "fxo_stage_method" not in columns:
        op.add_column("sip_trunks", sa.Column("fxo_stage_method", sa.String(length=1), nullable=False, server_default="2"))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("sip_trunks")}
    if "fxo_stage_method" in columns:
        op.drop_column("sip_trunks", "fxo_stage_method")
