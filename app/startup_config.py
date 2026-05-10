from app.config import get_settings
from app.database import SessionLocal, init_db
from app.services.asterisk import GENERATED_FILES, apply_revision, generate_config, render_configs
from app.services.auth import has_admin
from app.services.config_test import run_generated_config_test


def apply_startup_config() -> None:
    settings = get_settings()
    init_db()
    db = SessionLocal()
    try:
        if not has_admin(db):
            return
        if not run_generated_config_test(db, settings).ok:
            return
        if _active_config_matches_database(db, settings):
            return
        revision = generate_config(db, settings)
        apply_revision(db, revision, settings, reload_asterisk=False)
    finally:
        db.close()


def _active_config_matches_database(db, settings) -> bool:
    rendered = render_configs(db, settings)
    for filename in GENERATED_FILES:
        active_path = settings.asterisk_config_dir / filename
        if not active_path.exists() or active_path.read_text(encoding="utf-8") != rendered[filename]:
            return False
    return True


if __name__ == "__main__":
    apply_startup_config()
