"""voicemail greetings

Revision ID: 0006_voicemail_greetings
Revises: 0005_business_hours
Create Date: 2026-05-10 00:00:02.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0006_voicemail_greetings"
down_revision = "0005_business_hours"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("extensions", sa.Column("voicemail_greeting_mode", sa.String(length=20), nullable=False, server_default="default"))
    op.add_column("extensions", sa.Column("voicemail_greeting_text", sa.Text(), nullable=True))
    op.add_column("extensions", sa.Column("voicemail_greeting_audio_path", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("extensions", "voicemail_greeting_audio_path")
    op.drop_column("extensions", "voicemail_greeting_text")
    op.drop_column("extensions", "voicemail_greeting_mode")
