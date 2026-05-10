from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.models import IvrMenu
from app.services.auth import current_admin, has_admin
from app.services.diagnostics import check_dialplan_extension, collect_diagnostics, set_rtp_debug
from app.templating import templates

router = APIRouter(prefix="/diagnostics")


def _guard(request: Request, db: Session) -> RedirectResponse | None:
    if not has_admin(db):
        return RedirectResponse("/setup", status_code=303)
    if not current_admin(request, db):
        return RedirectResponse("/login", status_code=303)
    return None


@router.get("", response_class=HTMLResponse)
def show_diagnostics(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    guarded = _guard(request, db)
    if guarded:
        return guarded
    results = collect_diagnostics(settings)
    ivr_menus = list(db.query(IvrMenu).order_by(IvrMenu.number))
    for menu in ivr_menus:
        results.append(check_dialplan_extension(settings, menu.number))
    return templates.TemplateResponse(
        "diagnostics/index.html",
        {
            "request": request,
            "results": results,
            "asterisk_enabled": settings.asterisk_apply_enabled,
            "sip_port": settings.sip_port,
            "rtp_start": settings.rtp_start,
            "rtp_end": settings.rtp_end,
            "external_address": settings.external_address,
            "local_net": settings.local_net,
        },
    )


@router.post("/rtp-debug/{state}")
def toggle_rtp_debug(
    state: str,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    guarded = _guard(request, db)
    if guarded:
        return guarded
    if state in {"on", "off"}:
        set_rtp_debug(settings, enabled=state == "on")
    return RedirectResponse("/diagnostics", status_code=303)
