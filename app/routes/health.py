from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.services.auth import current_admin, has_admin
from app.services.config_test import run_generated_config_test
from app.services.health import collect_health
from app.templating import templates

router = APIRouter(prefix="/health")


def _guard(request: Request, db: Session) -> RedirectResponse | None:
    if not has_admin(db):
        return RedirectResponse("/setup", status_code=303)
    if not current_admin(request, db):
        return RedirectResponse("/login", status_code=303)
    return None


@router.get("", response_class=HTMLResponse)
def health_page(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    guarded = _guard(request, db)
    if guarded:
        return guarded
    health = collect_health(settings)
    config_test = run_generated_config_test(db, settings)
    return templates.TemplateResponse(
        "health/index.html",
        {
            "request": request,
            "health": health,
            "config_test": config_test,
            "asterisk_enabled": settings.asterisk_apply_enabled,
        },
    )


@router.get("/ready")
def readiness(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    database_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        database_ok = False
    asterisk_running = collect_health(settings).asterisk_running if settings.asterisk_apply_enabled else False
    status_code = 200 if database_ok else 503
    return JSONResponse(
        {
            "ok": status_code == 200,
            "web": True,
            "database": database_ok,
            "asterisk": asterisk_running,
        },
        status_code=status_code,
    )
