"""remove contacts

Revision ID: 0009_remove_contacts
Revises: 0008_pbx_settings
Create Date: 2026-05-10 00:00:05.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0009_remove_contacts"
down_revision = "0008_pbx_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "contacts" not in inspector.get_table_names():
        return
    indexes = {index["name"] for index in inspector.get_indexes("contacts")}
    if "ix_contacts_phone_number" in indexes:
        op.drop_index(op.f("ix_contacts_phone_number"), table_name="contacts")
    if "ix_contacts_name" in indexes:
        op.drop_index(op.f("ix_contacts_name"), table_name="contacts")
    op.drop_table("contacts")


def downgrade() -> None:
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
