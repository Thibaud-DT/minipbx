from collections.abc import Generator

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
connect_args = {"check_same_thread": False} if settings.resolved_database_url.startswith("sqlite") else {}
engine = create_engine(settings.resolved_database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app.models import admin, config_revision, extension, inbound_route, ivr, outbound_rule, pbx_settings, ring_group, sip_trunk  # noqa: F401

    if settings.migrations_enabled:
        _run_migrations()
    else:
        Base.metadata.create_all(bind=engine)
    _assert_required_schema()


def _run_migrations() -> None:
    from alembic import command
    from alembic.config import Config

    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", settings.resolved_database_url)
    command.upgrade(config, "head")


def _assert_required_schema() -> None:
    required_tables = {
        "users_admin",
        "extensions",
        "sip_trunks",
        "config_revisions",
        "pbx_settings",
        "inbound_routes",
        "ring_groups",
        "ring_group_members",
        "ivr_menus",
        "ivr_options",
        "outbound_rules",
    }
    inspector = inspect(engine)
    missing = sorted(required_tables - set(inspector.get_table_names()))
    if missing:
        raise RuntimeError(
            "Schema SQLite incomplet apres migrations. "
            f"Tables manquantes: {', '.join(missing)}. "
            "Verifie le volume /var/lib/minipbx et la table alembic_version."
        )
