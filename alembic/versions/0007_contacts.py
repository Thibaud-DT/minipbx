"""contacts

Revision ID: 0007_contacts
Revises: 0006_voicemail_greetings
Create Date: 2026-05-10 00:00:03.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0007_contacts"
down_revision = "0006_voicemail_greetings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("phone_number", sa.String(length=40), nullable=False),
        sa.Column("company", sa.String(length=120), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_contacts_name"), "contacts", ["name"], unique=False)
    op.create_index(op.f("ix_contacts_phone_number"), "contacts", ["phone_number"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_contacts_phone_number"), table_name="contacts")
    op.drop_index(op.f("ix_contacts_name"), table_name="contacts")
    op.drop_table("contacts")
