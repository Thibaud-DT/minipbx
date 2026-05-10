"""business hours

Revision ID: 0005_business_hours
Revises: 0004_ivr_menus
Create Date: 2026-05-10 00:00:01.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_business_hours"
down_revision = "0004_ivr_menus"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("inbound_routes", sa.Column("business_days", sa.String(length=80), nullable=False, server_default="mon,tue,wed,thu,fri"))
    op.add_column("inbound_routes", sa.Column("business_open_time", sa.String(length=5), nullable=False, server_default="09:00"))
    op.add_column("inbound_routes", sa.Column("business_close_time", sa.String(length=5), nullable=False, server_default="18:00"))
    op.add_column("inbound_routes", sa.Column("holiday_dates", sa.String(length=1000), nullable=True))


def downgrade() -> None:
    op.drop_column("inbound_routes", "holiday_dates")
    op.drop_column("inbound_routes", "business_close_time")
    op.drop_column("inbound_routes", "business_open_time")
    op.drop_column("inbound_routes", "business_days")
