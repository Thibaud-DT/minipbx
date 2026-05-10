import shutil
import subprocess
import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from urllib.parse import unquote, urlparse
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile

from app.config import Settings
from app.models import ConfigRevision
from app.services.asterisk import GENERATED_FILES, run_command

MAX_EXTRACTED_BACKUP_BYTES = 250 * 1024 * 1024


@dataclass(frozen=True)
class BackupFolder:
    name: str
    path: Path
    created_at: datetime | None
    file_count: int
    size_bytes: int


@dataclass(frozen=True)
class RestoreResult:
    backup_name: str
    restored_files: list[str]
    safety_backup_dir: Path
    reloaded: bool


@dataclass(frozen=True)
class FullBackupInspection:
    valid: bool
    message: str
    created_at: str | None
    entry_count: int
    has_database: bool
    generated_count: int
    asterisk_backup_count: int
    asterisk_current_count: int


@dataclass(frozen=True)
class FullBackupApplyResult:
    restored_generated_files: int
    restored_asterisk_backup_files: int
    restored_asterisk_current_files: list[str]
    staged_database_path: Path | None
    safety_backup_dir: Path | None
    reloaded: bool


@dataclass(frozen=True)
class StagedDatabase:
    name: str
    path: Path
    created_at: datetime | None
    size_bytes: int


@dataclass(frozen=True)
class DatabaseActivationResult:
    staged_database: Path
    active_database: Path
    previous_database_backup: Path | None
    restart_marker: Path


def list_backup_folders(settings: Settings) -> list[BackupFolder]:
    return _list_folders(settings.backup_dir)


def list_staged_databases(settings: Settings) -> list[StagedDatabase]:
    if not settings.import_dir.exists():
        return []
    staged = []
    for path in settings.import_dir.iterdir():
        if not path.is_dir() or path.name == "database-backups":
            continue
        database_path = path / "database" / "minipbx.db"
        if database_path.is_file():
            staged.append(
                StagedDatabase(
                    name=path.name,
                    path=database_path,
                    created_at=_timestamp_from_name(path.name),
                    size_bytes=database_path.stat().st_size,
                )
            )
    return sorted(staged, key=lambda item: item.created_at or datetime.min, reverse=True)


def revision_archive_bytes(revision: ConfigRevision) -> bytes:
    source_dir = Path(revision.generated_path)
    return _zip_directory(source_dir, f"minipbx-revision-{revision.id}")


def backup_archive_bytes(settings: Settings, backup_name: str) -> bytes:
    source_dir = _safe_child_dir(settings.backup_dir, backup_name)
    return _zip_directory(source_dir, f"minipbx-backup-{backup_name}")


def full_application_archive_bytes(settings: Settings) -> bytes:
    created_at = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    manifest = {
        "application": "MiniPBX",
        "created_at": created_at,
        "contains": [
            "manifest.json",
            "database/minipbx.db",
            "generated/",
            "asterisk-backups/",
            "asterisk-current/",
        ],
        "database_url_type": _database_url_type(settings.resolved_database_url),
    }
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        database_path = _sqlite_database_path(settings.resolved_database_url)
        if database_path and database_path.exists():
            archive.write(database_path, "database/minipbx.db")
        _write_directory_to_archive(archive, settings.generated_config_dir, "generated")
        _write_directory_to_archive(archive, settings.backup_dir, "asterisk-backups")
        for filename in GENERATED_FILES:
            path = settings.asterisk_config_dir / filename
            if path.exists():
                archive.write(path, Path("asterisk-current") / filename)
    return buffer.getvalue()


def inspect_full_application_archive(content: bytes) -> FullBackupInspection:
    try:
        with ZipFile(BytesIO(content)) as archive:
            names = archive.namelist()
            if "manifest.json" not in names:
                return _invalid_inspection("Archive invalide: manifest.json absent.", len(names))
            try:
                manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            except (KeyError, UnicodeDecodeError, json.JSONDecodeError):
                return _invalid_inspection("Archive invalide: manifest.json illisible.", len(names))
            if manifest.get("application") != "MiniPBX":
                return _invalid_inspection("Archive invalide: application MiniPBX non detectee.", len(names))
            total_size = sum(member.file_size for member in archive.infolist())
            if total_size > MAX_EXTRACTED_BACKUP_BYTES:
                return _invalid_inspection("Archive invalide: contenu decompresse trop volumineux.", len(names))
            return FullBackupInspection(
                valid=True,
                message="Archive MiniPBX valide. Aucune restauration n'a ete appliquee.",
                created_at=manifest.get("created_at"),
                entry_count=len(names),
                has_database="database/minipbx.db" in names,
                generated_count=_count_prefix(names, "generated/"),
                asterisk_backup_count=_count_prefix(names, "asterisk-backups/"),
                asterisk_current_count=_count_prefix(names, "asterisk-current/"),
            )
    except BadZipFile:
        return _invalid_inspection("Archive invalide: le fichier n'est pas un ZIP lisible.", 0)


def apply_full_application_archive(content: bytes, settings: Settings) -> FullBackupApplyResult:
    inspection = inspect_full_application_archive(content)
    if not inspection.valid:
        raise ValueError(inspection.message)

    settings.generated_config_dir.mkdir(parents=True, exist_ok=True)
    settings.backup_dir.mkdir(parents=True, exist_ok=True)
    settings.asterisk_config_dir.mkdir(parents=True, exist_ok=True)
    settings.import_dir.mkdir(parents=True, exist_ok=True)

    import_run_dir = _unique_backup_dir(settings.import_dir)
    import_run_dir.mkdir(parents=True, exist_ok=True)
    staged_database_path: Path | None = None
    safety_backup_dir: Path | None = None
    restored_generated_files = 0
    restored_asterisk_backup_files = 0
    restored_asterisk_current_files: list[str] = []
    original_asterisk_files: dict[str, Path | None] = {}

    with ZipFile(BytesIO(content)) as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue
            name = member.filename
            if name == "database/minipbx.db":
                staged_database_path = _safe_join(import_run_dir, "database/minipbx.db")
                _extract_member(archive, member, staged_database_path)
                continue
            if name.startswith("generated/"):
                target = _safe_join(settings.generated_config_dir, name.removeprefix("generated/"))
                _extract_member(archive, member, target)
                restored_generated_files += 1
                continue
            if name.startswith("asterisk-backups/"):
                target = _safe_join(settings.backup_dir, name.removeprefix("asterisk-backups/"))
                _extract_member(archive, member, target)
                restored_asterisk_backup_files += 1
                continue
            if name.startswith("asterisk-current/"):
                filename = Path(name).name
                if filename not in GENERATED_FILES:
                    continue
                if safety_backup_dir is None:
                    safety_backup_dir = _unique_backup_dir(settings.backup_dir)
                    safety_backup_dir.mkdir(parents=True, exist_ok=True)
                target = settings.asterisk_config_dir / filename
                if target.exists():
                    shutil.copy2(target, safety_backup_dir / filename)
                    original_asterisk_files[filename] = safety_backup_dir / filename
                else:
                    original_asterisk_files[filename] = None
                _extract_member(archive, member, target)
                restored_asterisk_current_files.append(filename)

    reloaded = False
    if restored_asterisk_current_files and settings.asterisk_apply_enabled:
        try:
            run_command(settings.asterisk_reload_command)
        except (OSError, subprocess.CalledProcessError) as exc:
            _restore_files(settings.asterisk_config_dir, original_asterisk_files)
            raise ValueError("Reload Asterisk en echec, ancienne configuration restauree.") from exc
        reloaded = True

    return FullBackupApplyResult(
        restored_generated_files=restored_generated_files,
        restored_asterisk_backup_files=restored_asterisk_backup_files,
        restored_asterisk_current_files=restored_asterisk_current_files,
        staged_database_path=staged_database_path,
        safety_backup_dir=safety_backup_dir,
        reloaded=reloaded,
    )


def activate_staged_database(settings: Settings, import_name: str) -> DatabaseActivationResult:
    staged_root = _safe_child_dir(settings.import_dir, import_name)
    staged_database = staged_root / "database" / "minipbx.db"
    if not staged_database.is_file():
        raise FileNotFoundError(import_name)
    _validate_sqlite_database(staged_database)

    active_database = _sqlite_database_path(settings.resolved_database_url)
    if active_database is None:
        raise ValueError("La bascule automatique exige une base SQLite locale.")

    settings.import_dir.mkdir(parents=True, exist_ok=True)
    active_database.parent.mkdir(parents=True, exist_ok=True)
    previous_database_backup = None
    if active_database.exists():
        backup_dir = _unique_backup_dir(settings.import_dir / "database-backups")
        backup_dir.mkdir(parents=True, exist_ok=True)
        previous_database_backup = backup_dir / active_database.name
        shutil.copy2(active_database, previous_database_backup)

    shutil.copy2(staged_database, active_database)
    restart_marker = settings.import_dir / "restart-required.txt"
    restart_marker.write_text(
        "Une base SQLite importee a ete activee. Redemarrer le conteneur MiniPBX avant de continuer.\n",
        encoding="utf-8",
    )
    return DatabaseActivationResult(
        staged_database=staged_database,
        active_database=active_database,
        previous_database_backup=previous_database_backup,
        restart_marker=restart_marker,
    )


def restore_asterisk_backup(settings: Settings, backup_name: str) -> RestoreResult:
    source_dir = _safe_child_dir(settings.backup_dir, backup_name)
    settings.asterisk_config_dir.mkdir(parents=True, exist_ok=True)
    settings.backup_dir.mkdir(parents=True, exist_ok=True)

    safety_backup_dir = _unique_backup_dir(settings.backup_dir)
    safety_backup_dir.mkdir(parents=True, exist_ok=True)

    restored_files = []
    original_files: dict[str, Path | None] = {}
    for filename in GENERATED_FILES:
        source = source_dir / filename
        if not source.exists():
            continue
        target = settings.asterisk_config_dir / filename
        if target.exists():
            shutil.copy2(target, safety_backup_dir / filename)
            original_files[filename] = safety_backup_dir / filename
        else:
            original_files[filename] = None
        shutil.copy2(source, target)
        restored_files.append(filename)

    if not restored_files:
        raise FileNotFoundError(f"Aucun fichier MiniPBX restaurable dans {backup_name}")

    reloaded = False
    if settings.asterisk_apply_enabled:
        try:
            run_command(settings.asterisk_reload_command)
        except (OSError, subprocess.CalledProcessError) as exc:
            _restore_files(settings.asterisk_config_dir, original_files)
            raise ValueError("Reload Asterisk en echec, ancienne configuration restauree.") from exc
        reloaded = True
    return RestoreResult(
        backup_name=backup_name,
        restored_files=restored_files,
        safety_backup_dir=safety_backup_dir,
        reloaded=reloaded,
    )


def _list_folders(root: Path) -> list[BackupFolder]:
    if not root.exists():
        return []
    folders = []
    for path in root.iterdir():
        if not path.is_dir():
            continue
        files = [item for item in path.rglob("*") if item.is_file()]
        folders.append(
            BackupFolder(
                name=path.name,
                path=path,
                created_at=_timestamp_from_name(path.name),
                file_count=len(files),
                size_bytes=sum(item.stat().st_size for item in files),
            )
        )
    return sorted(folders, key=lambda item: item.created_at or datetime.min, reverse=True)


def _safe_child_dir(root: Path, child_name: str) -> Path:
    candidate = (root / child_name).resolve()
    root_resolved = root.resolve()
    if not candidate.is_dir() or root_resolved not in candidate.parents:
        raise FileNotFoundError(child_name)
    return candidate


def _zip_directory(source_dir: Path, archive_root: str) -> bytes:
    if not source_dir.is_dir():
        raise FileNotFoundError(str(source_dir))
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        _write_directory_to_archive(archive, source_dir, archive_root)
    return buffer.getvalue()


def _write_directory_to_archive(archive: ZipFile, source_dir: Path, archive_root: str | Path) -> None:
    if not source_dir.is_dir():
        return
    for path in sorted(source_dir.rglob("*")):
        if path.is_file():
            archive.write(path, Path(archive_root) / path.relative_to(source_dir))


def _extract_member(archive: ZipFile, member, target: Path) -> None:
    if member.file_size > MAX_EXTRACTED_BACKUP_BYTES:
        raise ValueError("Archive invalide: fichier decompresse trop volumineux.")
    target.parent.mkdir(parents=True, exist_ok=True)
    with archive.open(member) as source, target.open("wb") as destination:
        shutil.copyfileobj(source, destination)


def _restore_files(target_dir: Path, original_files: dict[str, Path | None]) -> None:
    for filename, backup_path in original_files.items():
        target = target_dir / filename
        if backup_path is None:
            target.unlink(missing_ok=True)
        elif backup_path.exists():
            shutil.copy2(backup_path, target)


def _safe_join(root: Path, relative: str | Path) -> Path:
    relative_path = Path(relative)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise ValueError(f"Chemin invalide dans l'archive: {relative}")
    root_resolved = root.resolve()
    candidate = (root / relative_path).resolve()
    if candidate != root_resolved and root_resolved not in candidate.parents:
        raise ValueError(f"Chemin invalide dans l'archive: {relative}")
    return candidate


def _unique_backup_dir(root: Path) -> Path:
    base = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    candidate = root / base
    suffix = 1
    while candidate.exists():
        candidate = root / f"{base}-{suffix}"
        suffix += 1
    return candidate


def _timestamp_from_name(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, "%Y%m%d%H%M%S")
    except ValueError:
        return None


def _sqlite_database_path(database_url: str) -> Path | None:
    parsed = urlparse(database_url)
    if parsed.scheme != "sqlite":
        return None
    if parsed.path in {"", "/"} or parsed.path == ":memory:":
        return None
    return Path(unquote(parsed.path))


def _database_url_type(database_url: str) -> str:
    parsed = urlparse(database_url)
    return parsed.scheme or "unknown"


def _validate_sqlite_database(path: Path) -> None:
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
            result = connection.execute("PRAGMA integrity_check").fetchone()
    except sqlite3.DatabaseError as exc:
        raise ValueError("La base importee n'est pas une base SQLite valide.") from exc
    if not result or result[0] != "ok":
        raise ValueError("La base importee a echoue au controle d'integrite SQLite.")


def _count_prefix(names: list[str], prefix: str) -> int:
    return len([name for name in names if name.startswith(prefix) and not name.endswith("/")])


def _invalid_inspection(message: str, entry_count: int) -> FullBackupInspection:
    return FullBackupInspection(
        valid=False,
        message=message,
        created_at=None,
        entry_count=entry_count,
        has_database=False,
        generated_count=0,
        asterisk_backup_count=0,
        asterisk_current_count=0,
    )
