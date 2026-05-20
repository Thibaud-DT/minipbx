from pathlib import Path

from app.config import Settings
from app.models import ConfigRevision
from app.services.asterisk import GENERATED_FILES
from app.startup_config import _active_config_matches_revision


def test_active_config_matches_revision_detects_bootstrap_placeholders(tmp_path: Path):
    revision_dir = tmp_path / "revision"
    active_dir = tmp_path / "asterisk"
    revision_dir.mkdir()
    active_dir.mkdir()
    for filename in GENERATED_FILES:
        (revision_dir / filename).write_text(f"generated {filename}", encoding="utf-8")
        (active_dir / filename).write_text("; bootstrap placeholder", encoding="utf-8")
    revision = ConfigRevision(status="applied", generated_path=str(revision_dir))
    settings = Settings(
        secret_key="test",
        asterisk_config_dir=active_dir,
        asterisk_apply_enabled=False,
    )

    assert not _active_config_matches_revision(revision, settings)


def test_active_config_matches_revision_accepts_restored_files(tmp_path: Path):
    revision_dir = tmp_path / "revision"
    active_dir = tmp_path / "asterisk"
    revision_dir.mkdir()
    active_dir.mkdir()
    for filename in GENERATED_FILES:
        content = f"generated {filename}"
        (revision_dir / filename).write_text(content, encoding="utf-8")
        (active_dir / filename).write_text(content, encoding="utf-8")
    revision = ConfigRevision(status="applied", generated_path=str(revision_dir))
    settings = Settings(
        secret_key="test",
        asterisk_config_dir=active_dir,
        asterisk_apply_enabled=False,
    )

    assert _active_config_matches_revision(revision, settings)
