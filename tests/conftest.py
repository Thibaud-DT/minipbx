import os
from pathlib import Path

import pytest

os.environ.setdefault("MINIPBX_SECRET_KEY", "test-secret")
os.environ.setdefault("MINIPBX_DATA_DIR", "/tmp/minipbx-tests")
os.environ.setdefault("MINIPBX_DATABASE_URL", "sqlite:////tmp/minipbx-tests/minipbx.db")
os.environ.setdefault("MINIPBX_GENERATED_CONFIG_DIR", "/tmp/minipbx-tests/generated")
os.environ.setdefault("MINIPBX_PROMPT_DIR", "/tmp/minipbx-tests/prompts")
os.environ.setdefault("MINIPBX_BACKUP_DIR", "/tmp/minipbx-tests/backups")
os.environ.setdefault("MINIPBX_IMPORT_DIR", "/tmp/minipbx-tests/imports")
os.environ.setdefault("MINIPBX_ASTERISK_CONFIG_DIR", "/tmp/minipbx-tests/asterisk")
os.environ.setdefault("MINIPBX_CDR_CSV_PATH", "/tmp/minipbx-tests/cdr/Master.csv")
os.environ.setdefault("MINIPBX_VOICEMAIL_SPOOL_DIR", "/tmp/minipbx-tests/voicemail/default")
os.environ["MINIPBX_TTS_BACKEND"] = "none"
os.environ["MINIPBX_ASTERISK_APPLY_ENABLED"] = "false"
os.environ["MINIPBX_CSRF_ENABLED"] = "false"
os.environ["MINIPBX_MIGRATIONS_ENABLED"] = "false"

Path("/tmp/minipbx-tests").mkdir(parents=True, exist_ok=True)
db_path = Path("/tmp/minipbx-tests/minipbx.db")
if db_path.exists():
    db_path.unlink()


@pytest.fixture(autouse=True)
def clean_database():
    from app.database import Base, engine

    cdr_path = Path(os.environ["MINIPBX_CDR_CSV_PATH"])
    cdr_path.parent.mkdir(parents=True, exist_ok=True)
    if cdr_path.exists():
        cdr_path.unlink()
    backup_dir = Path(os.environ["MINIPBX_BACKUP_DIR"])
    backup_dir.mkdir(parents=True, exist_ok=True)
    for item in backup_dir.iterdir():
        if item.is_file():
            item.unlink()
        elif item.is_dir():
            for nested in sorted(item.rglob("*"), reverse=True):
                if nested.is_file():
                    nested.unlink()
                elif nested.is_dir():
                    nested.rmdir()
            item.rmdir()
    import_dir = Path(os.environ["MINIPBX_IMPORT_DIR"])
    import_dir.mkdir(parents=True, exist_ok=True)
    for item in import_dir.iterdir():
        if item.is_file():
            item.unlink()
        elif item.is_dir():
            for nested in sorted(item.rglob("*"), reverse=True):
                if nested.is_file():
                    nested.unlink()
                elif nested.is_dir():
                    nested.rmdir()
            item.rmdir()
    prompt_dir = Path(os.environ["MINIPBX_PROMPT_DIR"])
    prompt_dir.mkdir(parents=True, exist_ok=True)
    for item in prompt_dir.iterdir():
        if item.is_file():
            item.unlink()
    asterisk_dir = Path(os.environ["MINIPBX_ASTERISK_CONFIG_DIR"])
    asterisk_dir.mkdir(parents=True, exist_ok=True)
    for item in asterisk_dir.iterdir():
        if item.is_file():
            item.unlink()
    voicemail_dir = Path(os.environ["MINIPBX_VOICEMAIL_SPOOL_DIR"])
    voicemail_dir.mkdir(parents=True, exist_ok=True)
    for item in voicemail_dir.iterdir():
        if item.is_file():
            item.unlink()
        elif item.is_dir():
            for nested in sorted(item.rglob("*"), reverse=True):
                if nested.is_file():
                    nested.unlink()
                elif nested.is_dir():
                    nested.rmdir()
            item.rmdir()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
