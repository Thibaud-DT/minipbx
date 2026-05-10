from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.models import ConfigRevision, Extension, SipTrunk
from app.services.asterisk import apply_revision, generate_config, get_asterisk_status
from app.services.auth import current_admin, has_admin
from app.services.cdr import read_call_records
from app.services.config_test import run_generated_config_test
from app.services.config_validation import has_blocking_issues, validate_config
from app.templating import templates

router = APIRouter()


def _guard(request: Request, db: Session) -> RedirectResponse | None:
    if not has_admin(db):
        return RedirectResponse("/setup", status_code=303)
    if not current_admin(request, db):
        return RedirectResponse("/login", status_code=303)
    return None


@router.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    if not has_admin(db):
        return RedirectResponse("/setup", status_code=303)
    if current_admin(request, db):
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse("home.html", {"request": request})


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    guarded = _guard(request, db)
    if guarded:
        return guarded
    extension_count = db.scalar(select(func.count(Extension.id))) or 0
    extension_numbers = set(db.scalars(select(Extension.number)))
    trunk = db.scalar(select(SipTrunk).limit(1))
    last_revision = db.scalar(select(ConfigRevision).order_by(ConfigRevision.created_at.desc()).limit(1))
    status = get_asterisk_status(settings)
    recent_calls = read_call_records(settings.cdr_csv_path, extension_numbers, limit=5)
    config_issues = validate_config(db, settings)
    alerts = []
    if extension_count == 0:
        alerts.append("Aucune extension configuree.")
    if not trunk:
        alerts.append("Trunk SIP non configure.")
    if not last_revision or last_revision.status != "applied":
        alerts.append("Configuration generee non appliquee.")
    return templates.TemplateResponse(
        "dashboard/index.html",
        {
            "request": request,
            "extension_count": extension_count,
            "trunk": trunk,
            "last_revision": last_revision,
            "asterisk_status": status,
            "recent_calls": recent_calls,
            "alerts": alerts,
            "config_issues": config_issues,
        },
    )


@router.post("/config/generate")
def generate(
    request: Request,
    next_url: str = Form(""),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    guarded = _guard(request, db)
    if guarded:
        return guarded
    issues = validate_config(db, settings)
    if has_blocking_issues(issues):
        return RedirectResponse("/config/preview?validation=failed", status_code=303)
    if not run_generated_config_test(db, settings).ok:
        return RedirectResponse("/config/preview?test=failed", status_code=303)
    generate_config(db, settings)
    return RedirectResponse(_safe_next(next_url, "/dashboard"), status_code=303)


@router.post("/config/apply")
def apply_latest(
    request: Request,
    next_url: str = Form(""),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    guarded = _guard(request, db)
    if guarded:
        return guarded
    issues = validate_config(db, settings)
    if has_blocking_issues(issues):
        return RedirectResponse("/config/preview?validation=failed", status_code=303)
    if not run_generated_config_test(db, settings).ok:
        return RedirectResponse("/config/preview?test=failed", status_code=303)
    revision = db.scalar(select(ConfigRevision).order_by(ConfigRevision.created_at.desc()).limit(1))
    if revision:
        apply_revision(db, revision, settings)
    return RedirectResponse(_safe_next(next_url, "/dashboard"), status_code=303)


@router.post("/config/apply-current")
def apply_current(
    request: Request,
    next_url: str = Form(""),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    guarded = _guard(request, db)
    if guarded:
        return guarded
    issues = validate_config(db, settings)
    if has_blocking_issues(issues):
        return RedirectResponse(_safe_next(next_url, "/config/preview?validation=failed"), status_code=303)
    if not run_generated_config_test(db, settings).ok:
        return RedirectResponse(_safe_next(next_url, "/config/preview?test=failed"), status_code=303)
    revision = generate_config(db, settings)
    apply_revision(db, revision, settings)
    return RedirectResponse(_safe_next(next_url, "/dashboard"), status_code=303)


def _safe_next(next_url: str, fallback: str) -> str:
    return next_url if next_url.startswith("/") and not next_url.startswith("//") else fallback
