from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.models import Extension
from app.services.auth import current_admin, has_admin
from app.services.voicemail import delete_voicemail_message, list_voicemail_messages, resolve_voicemail_audio
from app.templating import templates

router = APIRouter(prefix="/voicemail")


def _guard(request: Request, db: Session) -> RedirectResponse | None:
    if not has_admin(db):
        return RedirectResponse("/setup", status_code=303)
    if not current_admin(request, db):
        return RedirectResponse("/login", status_code=303)
    return None


@router.get("", response_class=HTMLResponse)
def voicemail_index(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    guarded = _guard(request, db)
    if guarded:
        return guarded
    extensions = list(db.scalars(select(Extension).where(Extension.voicemail_enabled.is_(True)).order_by(Extension.number)))
    messages = list_voicemail_messages(settings.voicemail_spool_dir, extensions)
    return templates.TemplateResponse(
        "voicemail/index.html",
        {"request": request, "messages": messages, "spool_dir": settings.voicemail_spool_dir},
    )


@router.get("/{mailbox}/{folder}/{filename}")
def download_voicemail(
    mailbox: str,
    folder: str,
    filename: str,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    guarded = _guard(request, db)
    if guarded:
        return guarded
    path = resolve_voicemail_audio(settings.voicemail_spool_dir, mailbox, folder, filename)
    if not path:
        return RedirectResponse("/voicemail", status_code=303)
    return FileResponse(path, filename=filename)


@router.post("/{mailbox}/{folder}/{filename}/delete")
def delete_voicemail(
    mailbox: str,
    folder: str,
    filename: str,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    guarded = _guard(request, db)
    if guarded:
        return guarded
    delete_voicemail_message(settings.voicemail_spool_dir, mailbox, folder, filename)
    return RedirectResponse("/voicemail", status_code=303)
