from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.models import ConfigRevision
from app.services.asterisk import GENERATED_FILES, apply_revision, render_configs
from app.services.auth import current_admin, has_admin
from app.services.config_test import run_generated_config_test
from app.services.config_validation import has_blocking_issues, validate_config
from app.templating import templates

router = APIRouter(prefix="/config")


def _guard(request: Request, db: Session) -> RedirectResponse | None:
    if not has_admin(db):
        return RedirectResponse("/setup", status_code=303)
    if not current_admin(request, db):
        return RedirectResponse("/login", status_code=303)
    return None


@router.get("/preview", response_class=HTMLResponse)
def preview_config(
    request: Request,
    selected: str = "pjsip_minipbx.conf",
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    guarded = _guard(request, db)
    if guarded:
        return guarded
    configs = render_configs(db, settings)
    if selected not in configs:
        selected = "pjsip_minipbx.conf"
    validation_issues = validate_config(db, settings)
    config_test = run_generated_config_test(db, settings)
    last_revision = db.scalar(select(ConfigRevision).order_by(ConfigRevision.created_at.desc()).limit(1))
    revisions = list(db.scalars(select(ConfigRevision).order_by(ConfigRevision.created_at.desc()).limit(10)))
    generated_files = []
    if last_revision:
        revision_dir = Path(last_revision.generated_path)
        generated_files = [filename for filename in GENERATED_FILES if (revision_dir / filename).exists()]
    return templates.TemplateResponse(
        "config/preview.html",
        {
            "request": request,
            "configs": configs,
            "selected": selected,
            "content": configs[selected],
            "validation_issues": validation_issues,
            "config_test": config_test,
            "last_revision": last_revision,
            "revisions": revisions,
            "revision_files": {revision.id: _revision_files(revision) for revision in revisions},
            "generated_files": generated_files,
        },
    )


@router.post("/revisions/{revision_id}/apply")
def apply_config_revision(
    revision_id: int,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    guarded = _guard(request, db)
    if guarded:
        return guarded
    issues = validate_config(db, settings)
    if has_blocking_issues(issues):
        return RedirectResponse("/config/preview?validation=failed", status_code=303)
    config_test = run_generated_config_test(db, settings)
    if not config_test.ok:
        return RedirectResponse("/config/preview?test=failed", status_code=303)
    revision = db.get(ConfigRevision, revision_id)
    if not revision:
        return RedirectResponse("/config/preview", status_code=303)
    missing_files = [filename for filename in GENERATED_FILES if not (Path(revision.generated_path) / filename).exists()]
    if missing_files:
        revision.status = "invalid"
        revision.summary = f"Revision incomplete, fichiers manquants: {', '.join(missing_files)}"
        db.add(revision)
        db.commit()
        return RedirectResponse("/config/preview", status_code=303)
    apply_revision(db, revision, settings)
    return RedirectResponse("/config/preview", status_code=303)


def _revision_files(revision: ConfigRevision) -> list[str]:
    revision_dir = Path(revision.generated_path)
    return [filename for filename in GENERATED_FILES if (revision_dir / filename).exists()]
