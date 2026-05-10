import asyncio

from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import SessionLocal, get_db
from app.models import AdminUser
from app.services.ami import ami_event_hub
from app.services.auth import SESSION_ADMIN_ID, current_admin, has_admin
from app.services.monitoring import collect_monitoring_snapshot
from app.templating import templates

router = APIRouter(prefix="/monitoring")


def _guard(request: Request, db: Session) -> RedirectResponse | None:
    if not has_admin(db):
        return RedirectResponse("/setup", status_code=303)
    if not current_admin(request, db):
        return RedirectResponse("/login", status_code=303)
    return None


@router.get("", response_class=HTMLResponse)
def monitoring_page(request: Request, db: Session = Depends(get_db)):
    guarded = _guard(request, db)
    if guarded:
        return guarded
    return templates.TemplateResponse("monitoring/index.html", {"request": request})


@router.get("/live", response_class=HTMLResponse)
def monitoring_live(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    guarded = _guard(request, db)
    if guarded:
        return guarded
    snapshot = collect_monitoring_snapshot(db, settings)
    return templates.TemplateResponse(
        "monitoring/live.html",
        {
            "request": request,
            "snapshot": snapshot,
        },
    )


@router.websocket("/ws")
async def monitoring_ws(websocket: WebSocket):
    await websocket.accept()
    settings = get_settings()
    admin_id = websocket.session.get(SESSION_ADMIN_ID)
    if not admin_id:
        await websocket.close(code=1008)
        return
    try:
        heartbeat = 0
        while True:
            payload = await asyncio.to_thread(_snapshot_payload, settings, admin_id)
            if payload is None:
                await websocket.close(code=1008)
                return
            ami_state = ami_event_hub.snapshot()
            payload["ami"] = {
                "connected": ami_state.connected,
                "last_event": ami_state.last_event,
                "event_count": ami_state.event_count,
            }
            await websocket.send_json(payload)
            heartbeat += 1
            await ami_event_hub.wait_for_update(timeout=5 if heartbeat > 0 else 1)
    except WebSocketDisconnect:
        return


def _snapshot_payload(settings: Settings, admin_id: int) -> dict | None:
    with SessionLocal() as db:
        if not has_admin(db) or not db.get(AdminUser, admin_id):
            return None
        return collect_monitoring_snapshot(db, settings).as_dict()
