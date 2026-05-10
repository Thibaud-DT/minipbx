import os
import json
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from tests.test_auth_flow import create_logged_client


def test_backup_page_downloads_revision_zip():
    client = create_logged_client()
    generated = client.post("/config/generate", follow_redirects=False)
    assert generated.status_code == 303

    page = client.get("/backups")
    assert page.status_code == 200
    assert "Revisions de configuration generees" in page.text

    archive = client.get("/backups/revisions/1.zip")
    assert archive.status_code == 200
    assert archive.headers["content-disposition"] == "attachment; filename=minipbx-revision-1.zip"
    with ZipFile(BytesIO(archive.content)) as zip_file:
        assert "minipbx-revision-1/pjsip_minipbx.conf" in zip_file.namelist()


def test_full_backup_download_contains_database_manifest_and_configs():
    client = create_logged_client()
    client.post("/config/generate", follow_redirects=False)
    backup_root = Path(os.environ["MINIPBX_BACKUP_DIR"])
    backup_dir = backup_root / "20260509120000"
    backup_dir.mkdir(parents=True, exist_ok=True)
    (backup_dir / "pjsip_minipbx.conf").write_text("; previous config\n", encoding="utf-8")
    asterisk_dir = Path(os.environ["MINIPBX_ASTERISK_CONFIG_DIR"])
    asterisk_dir.mkdir(parents=True, exist_ok=True)
    (asterisk_dir / "pjsip_minipbx.conf").write_text("; current config\n", encoding="utf-8")

    archive = client.get("/backups/full.zip")

    assert archive.status_code == 200
    assert archive.headers["content-disposition"] == "attachment; filename=minipbx-full-backup.zip"
    with ZipFile(BytesIO(archive.content)) as zip_file:
        names = zip_file.namelist()
        assert "manifest.json" in names
        assert "database/minipbx.db" in names
        assert "asterisk-backups/20260509120000/pjsip_minipbx.conf" in names
        assert "asterisk-current/pjsip_minipbx.conf" in names
        assert any(name.endswith("/pjsip_minipbx.conf") and name.startswith("generated/") for name in names)


def test_inspect_full_backup_upload_reports_archive_contents():
    client = create_logged_client()
    client.post("/config/generate", follow_redirects=False)
    archive = client.get("/backups/full.zip")

    inspected = client.post(
        "/backups/inspect",
        files={"backup_file": ("minipbx-full-backup.zip", archive.content, "application/zip")},
    )

    assert inspected.status_code == 200
    assert "Archive MiniPBX valide" in inspected.text
    assert "Base SQLite" in inspected.text
    assert "Presente" in inspected.text


def test_inspect_full_backup_rejects_invalid_zip():
    client = create_logged_client()

    inspected = client.post(
        "/backups/inspect",
        files={"backup_file": ("broken.zip", b"not a zip", "application/zip")},
    )

    assert inspected.status_code == 400
    assert "pas un ZIP lisible" in inspected.text


def test_apply_full_backup_requires_confirmation_and_stages_database():
    client = create_logged_client()
    client.post("/config/generate", follow_redirects=False)
    asterisk_dir = Path(os.environ["MINIPBX_ASTERISK_CONFIG_DIR"])
    import_dir = Path(os.environ["MINIPBX_IMPORT_DIR"])
    asterisk_dir.mkdir(parents=True, exist_ok=True)
    (asterisk_dir / "pjsip_minipbx.conf").write_text("; archive current config\n", encoding="utf-8")
    archive = client.get("/backups/full.zip")
    (asterisk_dir / "pjsip_minipbx.conf").write_text("; local current config\n", encoding="utf-8")

    refused = client.post(
        "/backups/apply-full",
        files={"backup_file": ("minipbx-full-backup.zip", archive.content, "application/zip")},
    )

    assert refused.status_code == 400
    assert "confirmation" in refused.text
    assert (asterisk_dir / "pjsip_minipbx.conf").read_text(encoding="utf-8") == "; local current config\n"

    applied = client.post(
        "/backups/apply-full",
        data={"confirm_restore": "on"},
        files={"backup_file": ("minipbx-full-backup.zip", archive.content, "application/zip")},
    )

    assert applied.status_code == 200
    assert "Sauvegarde complete appliquee" in applied.text
    assert "Base SQLite importee en attente" in applied.text
    assert (asterisk_dir / "pjsip_minipbx.conf").read_text(encoding="utf-8") == "; archive current config\n"
    staged_databases = list(import_dir.glob("*/database/minipbx.db"))
    assert staged_databases


def test_activate_staged_database_requires_confirmation_and_writes_restart_marker():
    client = create_logged_client()
    client.post("/config/generate", follow_redirects=False)
    import_dir = Path(os.environ["MINIPBX_IMPORT_DIR"])
    archive = client.get("/backups/full.zip")
    applied = client.post(
        "/backups/apply-full",
        data={"confirm_restore": "on"},
        files={"backup_file": ("minipbx-full-backup.zip", archive.content, "application/zip")},
    )
    assert applied.status_code == 200
    staged_database = next(import_dir.glob("*/database/minipbx.db"))
    import_name = staged_database.parents[1].name

    refused = client.post(f"/backups/activate-database/{import_name}")
    assert refused.status_code == 400
    assert "confirmation" in refused.text

    activated = client.post(
        f"/backups/activate-database/{import_name}",
        data={"confirm_restore": "on"},
    )

    assert activated.status_code == 200
    assert "Base importee activee" in activated.text
    assert "Redemarre le conteneur MiniPBX" in activated.text
    assert "docker compose restart minipbx" in activated.text
    assert (import_dir / "restart-required.txt").exists()
    assert list((import_dir / "database-backups").glob("*/minipbx.db"))


def test_backup_page_shows_persistent_restart_marker():
    client = create_logged_client()
    import_dir = Path(os.environ["MINIPBX_IMPORT_DIR"])
    import_dir.mkdir(parents=True, exist_ok=True)
    (import_dir / "restart-required.txt").write_text("restart\n", encoding="utf-8")

    page = client.get("/backups")

    assert page.status_code == 200
    assert "Redemarrage requis" in page.text
    assert "docker compose restart minipbx" in page.text


def test_inspect_full_backup_rejects_decompressed_archive_too_large(monkeypatch):
    from app.services import backups

    client = create_logged_client()
    monkeypatch.setattr(backups, "MAX_EXTRACTED_BACKUP_BYTES", 32)
    archive = _full_backup_archive(extra_files={"generated/oversized.txt": b"x" * 64})

    inspected = client.post(
        "/backups/inspect",
        files={"backup_file": ("oversized.zip", archive, "application/zip")},
    )

    assert inspected.status_code == 400
    assert "decompresse trop volumineux" in inspected.text


def test_apply_full_backup_rejects_path_traversal_archive():
    client = create_logged_client()
    archive = _full_backup_archive(extra_files={"generated/../evil.conf": b"bad"})

    applied = client.post(
        "/backups/apply-full",
        data={"confirm_restore": "on"},
        files={"backup_file": ("traversal.zip", archive, "application/zip")},
    )

    assert applied.status_code == 400
    assert "Chemin invalide" in applied.text


def test_backup_page_downloads_asterisk_backup_zip():
    client = create_logged_client()
    backup_root = Path(os.environ["MINIPBX_BACKUP_DIR"])
    backup_dir = backup_root / "20260509120000"
    backup_dir.mkdir(parents=True, exist_ok=True)
    (backup_dir / "pjsip_minipbx.conf").write_text("; previous config\n", encoding="utf-8")

    page = client.get("/backups")
    assert page.status_code == 200
    assert "20260509120000" in page.text

    archive = client.get("/backups/asterisk/20260509120000.zip")
    assert archive.status_code == 200
    with ZipFile(BytesIO(archive.content)) as zip_file:
        assert "minipbx-backup-20260509120000/pjsip_minipbx.conf" in zip_file.namelist()


def test_backup_download_rejects_unknown_folder():
    client = create_logged_client()

    response = client.get("/backups/asterisk/does-not-exist.zip", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/backups"


def test_restore_backup_requires_confirmation_and_restores_files():
    client = create_logged_client()
    backup_root = Path(os.environ["MINIPBX_BACKUP_DIR"])
    asterisk_dir = Path(os.environ["MINIPBX_ASTERISK_CONFIG_DIR"])
    backup_dir = backup_root / "20260509123000"
    backup_dir.mkdir(parents=True, exist_ok=True)
    (backup_dir / "pjsip_minipbx.conf").write_text("; restored config\n", encoding="utf-8")
    asterisk_dir.mkdir(parents=True, exist_ok=True)
    (asterisk_dir / "pjsip_minipbx.conf").write_text("; current config\n", encoding="utf-8")

    refused = client.post("/backups/asterisk/20260509123000/restore")
    assert refused.status_code == 400
    assert "case de confirmation" in refused.text
    assert (asterisk_dir / "pjsip_minipbx.conf").read_text(encoding="utf-8") == "; current config\n"

    restored = client.post(
        "/backups/asterisk/20260509123000/restore",
        data={"confirm_restore": "on"},
    )

    assert restored.status_code == 200
    assert "restauree" in restored.text
    assert (asterisk_dir / "pjsip_minipbx.conf").read_text(encoding="utf-8") == "; restored config\n"
    safety_backups = [path for path in backup_root.iterdir() if path.is_dir() and path.name != "20260509123000"]
    assert safety_backups
    assert (safety_backups[0] / "pjsip_minipbx.conf").read_text(encoding="utf-8") == "; current config\n"


def test_restore_backup_rolls_back_when_reload_fails():
    from app.config import Settings
    from app.services.backups import restore_asterisk_backup

    backup_root = Path(os.environ["MINIPBX_BACKUP_DIR"])
    asterisk_dir = Path(os.environ["MINIPBX_ASTERISK_CONFIG_DIR"])
    backup_dir = backup_root / "20260509124500"
    backup_dir.mkdir(parents=True, exist_ok=True)
    (backup_dir / "pjsip_minipbx.conf").write_text("; restored config\n", encoding="utf-8")
    asterisk_dir.mkdir(parents=True, exist_ok=True)
    (asterisk_dir / "pjsip_minipbx.conf").write_text("; current config\n", encoding="utf-8")

    settings = Settings(
        secret_key="test",
        data_dir=Path(os.environ["MINIPBX_DATA_DIR"]),
        backup_dir=backup_root,
        asterisk_config_dir=asterisk_dir,
        asterisk_apply_enabled=True,
        asterisk_reload_command="false",
    )

    try:
        restore_asterisk_backup(settings, "20260509124500")
    except ValueError as exc:
        assert "ancienne configuration restauree" in str(exc)
    else:
        raise AssertionError("restore_asterisk_backup should fail when reload command fails")

    assert (asterisk_dir / "pjsip_minipbx.conf").read_text(encoding="utf-8") == "; current config\n"


def _full_backup_archive(extra_files: dict[str, bytes] | None = None) -> bytes:
    manifest = {
        "application": "MiniPBX",
        "created_at": "2026-05-10T00:00:00Z",
        "contains": ["manifest.json"],
        "database_url_type": "sqlite",
    }
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        for name, content in (extra_files or {}).items():
            archive.writestr(name, content)
    return buffer.getvalue()
