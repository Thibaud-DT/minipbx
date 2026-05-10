from fastapi import APIRouter, Depends, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.models import ConfigRevision
from app.services.auth import current_admin, has_admin
from app.services.backups import (
    activate_staged_database,
    backup_archive_bytes,
    apply_full_application_archive,
    full_application_archive_bytes,
    inspect_full_application_archive,
    list_backup_folders,
    list_staged_databases,
    restore_asterisk_backup,
    revision_archive_bytes,
)
from app.templating import templates

router = APIRouter(prefix="/backups")
MAX_IMPORT_SIZE_BYTES = 50 * 1024 * 1024


def _guard(request: Request, db: Session) -> RedirectResponse | None:
    if not has_admin(db):
        return RedirectResponse("/setup", status_code=303)
    if not current_admin(request, db):
        return RedirectResponse("/login", status_code=303)
    return None


@router.get("", response_class=HTMLResponse)
def list_backups(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    guarded = _guard(request, db)
    if guarded:
        return guarded
    return _backups_page(request, db, settings)


@router.get("/revisions/{revision_id}.zip")
def download_revision(
    revision_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    guarded = _guard(request, db)
    if guarded:
        return guarded
    revision = db.get(ConfigRevision, revision_id)
    if not revision:
        return RedirectResponse("/backups", status_code=303)
    return _zip_response(revision_archive_bytes(revision), f"minipbx-revision-{revision.id}.zip")


@router.get("/asterisk/{backup_name}.zip")
def download_backup(
    backup_name: str,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    guarded = _guard(request, db)
    if guarded:
        return guarded
    try:
        content = backup_archive_bytes(settings, backup_name)
    except FileNotFoundError:
        return RedirectResponse("/backups", status_code=303)
    return _zip_response(content, f"minipbx-asterisk-backup-{backup_name}.zip")


@router.get("/full.zip")
def download_full_backup(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    guarded = _guard(request, db)
    if guarded:
        return guarded
    return _zip_response(full_application_archive_bytes(settings), "minipbx-full-backup.zip")


@router.post("/inspect", response_class=HTMLResponse)
async def inspect_full_backup(
    request: Request,
    backup_file: UploadFile,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    guarded = _guard(request, db)
    if guarded:
        return guarded
    content = await backup_file.read()
    if len(content) > MAX_IMPORT_SIZE_BYTES:
        return _backups_page(
            request,
            db,
            settings,
            error="Archive trop volumineuse pour inspection.",
            status_code=400,
        )
    inspection = inspect_full_application_archive(content)
    return _backups_page(
        request,
        db,
        settings,
        import_report=inspection,
        error=None if inspection.valid else inspection.message,
        status_code=200 if inspection.valid else 400,
    )


@router.post("/apply-full", response_class=HTMLResponse)
async def apply_full_backup(
    request: Request,
    backup_file: UploadFile,
    confirm_restore: bool = Form(False),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    guarded = _guard(request, db)
    if guarded:
        return guarded
    if not confirm_restore:
        return _backups_page(
            request,
            db,
            settings,
            error="La case de confirmation est obligatoire avant application d'une sauvegarde complete.",
            status_code=400,
        )
    content = await backup_file.read()
    if len(content) > MAX_IMPORT_SIZE_BYTES:
        return _backups_page(request, db, settings, error="Archive trop volumineuse pour application.", status_code=400)
    try:
        result = apply_full_application_archive(content, settings)
    except (ValueError, FileNotFoundError) as exc:
        return _backups_page(request, db, settings, error=str(exc), status_code=400)
    notice = (
        "Sauvegarde complete appliquee: "
        f"{result.restored_generated_files} fichier(s) de revision, "
        f"{result.restored_asterisk_backup_files} fichier(s) de backup Asterisk, "
        f"{len(result.restored_asterisk_current_files)} fichier(s) Asterisk actif(s)."
    )
    if result.staged_database_path:
        notice += f" Base SQLite importee en attente: {result.staged_database_path}."
    if result.safety_backup_dir:
        notice += f" Sauvegarde de securite: {result.safety_backup_dir}."
    return _backups_page(request, db, settings, notice=notice)


@router.post("/activate-database/{import_name}", response_class=HTMLResponse)
def activate_database_import(
    import_name: str,
    request: Request,
    confirm_restore: bool = Form(False),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    guarded = _guard(request, db)
    if guarded:
        return guarded
    if not confirm_restore:
        return _backups_page(
            request,
            db,
            settings,
            error="La case de confirmation est obligatoire avant activation d'une base importee.",
            status_code=400,
        )
    try:
        result = activate_staged_database(settings, import_name)
    except (FileNotFoundError, ValueError) as exc:
        return _backups_page(request, db, settings, error=str(exc), status_code=400)
    notice = (
        f"Base importee activee depuis {result.staged_database}. "
        f"Base precedente sauvegardee: {result.previous_database_backup}. "
        "Redemarre le conteneur MiniPBX avant de continuer."
    )
    return _backups_page(request, db, settings, notice=notice)


@router.post("/asterisk/{backup_name}/restore", response_class=HTMLResponse)
def restore_backup(
    backup_name: str,
    request: Request,
    confirm_restore: bool = Form(False),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    guarded = _guard(request, db)
    if guarded:
        return guarded
    if not confirm_restore:
        return _backups_page(
            request,
            db,
            settings,
            error="La case de confirmation est obligatoire avant restauration.",
            status_code=400,
        )
    try:
        result = restore_asterisk_backup(settings, backup_name)
    except FileNotFoundError:
        return _backups_page(request, db, settings, error="Sauvegarde introuvable ou invalide.", status_code=404)
    except ValueError as exc:
        return _backups_page(request, db, settings, error=str(exc), status_code=400)
    return _backups_page(
        request,
        db,
        settings,
        notice=(
            f"Sauvegarde {result.backup_name} restauree: {len(result.restored_files)} fichier(s). "
            f"Sauvegarde de securite: {result.safety_backup_dir}."
        ),
    )


def _backups_page(
    request: Request,
    db: Session,
    settings: Settings,
    notice: str | None = None,
    error: str | None = None,
    import_report=None,
    status_code: int = 200,
):
    revisions = list(db.scalars(select(ConfigRevision).order_by(ConfigRevision.created_at.desc())))
    backup_folders = list_backup_folders(settings)
    staged_databases = list_staged_databases(settings)
    return templates.TemplateResponse(
        "backups/index.html",
        {
            "request": request,
            "revisions": revisions,
            "backup_folders": backup_folders,
            "staged_databases": staged_databases,
            "generated_config_dir": settings.generated_config_dir,
            "backup_dir": settings.backup_dir,
            "restart_required": (settings.import_dir / "restart-required.txt").exists(),
            "notice": notice,
            "error": error,
            "import_report": import_report,
        },
        status_code=status_code,
    )


def _zip_response(content: bytes, filename: str) -> Response:
    return Response(
        content,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
