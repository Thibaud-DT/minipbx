from logging.config import fileConfig

from alembic import context
from sqlalchemy import inspect, text

from app.config import get_settings
from app.database import Base
from app.models import admin, config_revision, extension, inbound_route, ivr, outbound_rule, pbx_settings, ring_group, sip_trunk  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=get_settings().resolved_database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    from sqlalchemy import create_engine

    connectable = create_engine(get_settings().resolved_database_url)
    with connectable.connect() as connection:
        _stamp_legacy_schema(connection)
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


def _stamp_legacy_schema(connection) -> None:
    inspector = inspect(connection)
    table_names = set(inspector.get_table_names())
    if not table_names:
        return
    if "alembic_version" not in table_names:
        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        connection.execute(text("INSERT INTO alembic_version (version_num) VALUES (:version)"), {"version": _detect_schema_revision(inspector, table_names)})
        connection.commit()
        return
    current = connection.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).scalar()
    if current:
        return
    connection.execute(text("INSERT INTO alembic_version (version_num) VALUES (:version)"), {"version": _detect_schema_revision(inspector, table_names)})
    connection.commit()


def _detect_schema_revision(inspector, table_names: set[str]) -> str:
    """Best-effort stamp for databases created before Alembic was introduced."""
    if "sip_trunks" in table_names:
        sip_trunk_columns = {column["name"] for column in inspector.get_columns("sip_trunks")}
        if "inbound_match" in sip_trunk_columns:
            return "0010_trunk_inbound_match"
    if "contacts" not in table_names and "pbx_settings" in table_names:
        return "0009_remove_contacts"
    return "0008_pbx_settings"


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
