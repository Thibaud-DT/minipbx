import re

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import Extension, RingGroup, RingGroupMember
from app.services.auth import current_admin, has_admin
from app.templating import templates

router = APIRouter(prefix="/ring-groups")
NUMBER_RE = re.compile(r"^\d{2,6}$")
FALLBACK_TYPES = {"hangup", "extension", "voicemail"}


def _guard(request: Request, db: Session) -> RedirectResponse | None:
    if not has_admin(db):
        return RedirectResponse("/setup", status_code=303)
    if not current_admin(request, db):
        return RedirectResponse("/login", status_code=303)
    return None


@router.get("", response_class=HTMLResponse)
def list_ring_groups(request: Request, db: Session = Depends(get_db)):
    guarded = _guard(request, db)
    if guarded:
        return guarded
    ring_groups = list(
        db.scalars(
            select(RingGroup)
            .options(selectinload(RingGroup.members).selectinload(RingGroupMember.extension))
            .order_by(RingGroup.number)
        )
    )
    extensions = list(db.scalars(select(Extension).where(Extension.enabled.is_(True)).order_by(Extension.number)))
    return templates.TemplateResponse(
        "ring_groups/list.html",
        {"request": request, "ring_groups": ring_groups, "extensions": extensions},
    )


@router.post("")
def create_ring_group(
    request: Request,
    name: str = Form(...),
    number: str = Form(...),
    timeout_seconds: int = Form(20),
    fallback_type: str = Form("hangup"),
    fallback_target: str = Form(""),
    member_ids: list[int] = Form([]),
    next_url: str = Form(""),
    db: Session = Depends(get_db),
):
    guarded = _guard(request, db)
    if guarded:
        return guarded
    error = _validate_ring_group(db, number, timeout_seconds, fallback_type, fallback_target, member_ids)
    if error:
        return _list_with_error(request, db, error)
    ring_group = RingGroup(
        name=name.strip(),
        number=number.strip(),
        timeout_seconds=timeout_seconds,
        fallback_type=fallback_type,
        fallback_target=fallback_target.strip() or None,
    )
    ring_group.members = [RingGroupMember(extension_id=extension_id) for extension_id in member_ids]
    db.add(ring_group)
    db.commit()
    return RedirectResponse(_safe_next(next_url, "/ring-groups"), status_code=303)


@router.post("/{ring_group_id}/delete")
def delete_ring_group(
    ring_group_id: int,
    request: Request,
    next_url: str = Form(""),
    db: Session = Depends(get_db),
):
    guarded = _guard(request, db)
    if guarded:
        return guarded
    ring_group = db.get(RingGroup, ring_group_id)
    if ring_group:
        db.delete(ring_group)
        db.commit()
    return RedirectResponse(_safe_next(next_url, "/ring-groups"), status_code=303)


def _validate_ring_group(
    db: Session,
    number: str,
    timeout_seconds: int,
    fallback_type: str,
    fallback_target: str,
    member_ids: list[int],
) -> str | None:
    if not NUMBER_RE.match(number):
        return "Le numero du groupe doit contenir 2 a 6 chiffres."
    if db.scalar(select(Extension.id).where(Extension.number == number)):
        return "Ce numero est deja utilise par une extension."
    if db.scalar(select(RingGroup.id).where(RingGroup.number == number)):
        return "Ce numero de groupe existe deja."
    if timeout_seconds < 5 or timeout_seconds > 120:
        return "Le timeout doit etre compris entre 5 et 120 secondes."
    if fallback_type not in FALLBACK_TYPES:
        return "Destination de secours invalide."
    if fallback_type in {"extension", "voicemail"} and not fallback_target.strip():
        return "La destination de secours est obligatoire."
    if not member_ids:
        return "Le groupe doit contenir au moins une extension."
    return None


def _list_with_error(request: Request, db: Session, error: str) -> HTMLResponse:
    ring_groups = list(
        db.scalars(
            select(RingGroup)
            .options(selectinload(RingGroup.members).selectinload(RingGroupMember.extension))
            .order_by(RingGroup.number)
        )
    )


def _safe_next(next_url: str, fallback: str) -> str:
    return next_url if next_url.startswith("/") and not next_url.startswith("//") else fallback
    extensions = list(db.scalars(select(Extension).where(Extension.enabled.is_(True)).order_by(Extension.number)))
    return templates.TemplateResponse(
        "ring_groups/list.html",
        {"request": request, "ring_groups": ring_groups, "extensions": extensions, "error": error},
        status_code=400,
    )
