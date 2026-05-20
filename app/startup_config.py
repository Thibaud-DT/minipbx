from pathlib import Path

from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal, init_db
from app.models import ConfigRevision
from app.services.asterisk import GENERATED_FILES, apply_revision, generate_config, render_configs
from app.services.auth import has_admin
from app.services.config_test import run_generated_config_test


def apply_startup_config() -> None:
    settings = get_settings()
    init_db()
    db = SessionLocal()
    try:
        if not has_admin(db):
            print("MiniPBX startup config: no admin yet, keeping empty bootstrap config.")
            return
        last_applied = _last_applied_revision(db)
        if last_applied and not _active_config_matches_revision(last_applied, settings):
            print(f"MiniPBX startup config: restoring applied revision {last_applied.id}.")
            apply_revision(db, last_applied, settings, reload_asterisk=False)
        if _active_config_matches_database(db, settings):
            print("MiniPBX startup config: active config already matches database.")
            return
        config_test = run_generated_config_test(db, settings)
        if not config_test.ok:
            messages = "; ".join(check.message for check in config_test.checks if check.blocking)
            print(f"MiniPBX startup config: generated config invalid, keeping last applied revision. {messages}")
            return
        revision = generate_config(db, settings)
        print(f"MiniPBX startup config: applying generated revision {revision.id} before Asterisk start.")
        apply_revision(db, revision, settings, reload_asterisk=False)
    finally:
        db.close()


def _last_applied_revision(db) -> ConfigRevision | None:
    return db.scalar(select(ConfigRevision).where(ConfigRevision.status == "applied").order_by(ConfigRevision.created_at.desc()).limit(1))


def _active_config_matches_revision(revision: ConfigRevision, settings) -> bool:
    revision_dir = Path(revision.generated_path)
    for filename in GENERATED_FILES:
        active_path = settings.asterisk_config_dir / filename
        revision_path = revision_dir / filename
        if not active_path.exists() or not revision_path.exists():
            return False
        if active_path.read_text(encoding="utf-8") != revision_path.read_text(encoding="utf-8"):
            return False
    return True


def _active_config_matches_database(db, settings) -> bool:
    rendered = render_configs(db, settings)
    for filename in GENERATED_FILES:
        active_path = settings.asterisk_config_dir / filename
        if not active_path.exists() or active_path.read_text(encoding="utf-8") != rendered[filename]:
            return False
    return True


if __name__ == "__main__":
    apply_startup_config()
