import re

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import OutboundRule, SipTrunk
from app.services.auth import current_admin, has_admin
from app.templating import templates

router = APIRouter(prefix="/outbound")
PREFIX_RE = re.compile(r"^\d{0,4}$")
EMERGENCY_RE = re.compile(r"^\d{2,6}$")


def _guard(request: Request, db: Session) -> RedirectResponse | None:
    if not has_admin(db):
        return RedirectResponse("/setup", status_code=303)
    if not current_admin(request, db):
        return RedirectResponse("/login", status_code=303)
    return None


@router.get("", response_class=HTMLResponse)
def outbound_form(request: Request, db: Session = Depends(get_db)):
    guarded = _guard(request, db)
    if guarded:
        return guarded
    rule = db.scalar(select(OutboundRule).order_by(OutboundRule.id).limit(1))
    trunk = db.scalar(select(SipTrunk).where(SipTrunk.enabled.is_(True)).limit(1))
    return templates.TemplateResponse("outbound/form.html", {"request": request, "rule": rule, "trunk": trunk})


@router.post("")
def save_outbound_rule(
    request: Request,
    name: str = Form("Regles sortantes principales"),
    prefix: str = Form(""),
    emergency_numbers: str = Form("15,17,18,112"),
    allow_national: bool = Form(False),
    allow_mobile: bool = Form(False),
    allow_international: bool = Form(False),
    next_url: str = Form(""),
    db: Session = Depends(get_db),
):
    guarded = _guard(request, db)
    if guarded:
        return guarded
    error = _validate(prefix, emergency_numbers)
    rule = db.scalar(select(OutboundRule).order_by(OutboundRule.id).limit(1))
    trunk = db.scalar(select(SipTrunk).where(SipTrunk.enabled.is_(True)).limit(1))
    if error:
        return templates.TemplateResponse(
            "outbound/form.html",
            {"request": request, "rule": rule, "trunk": trunk, "error": error},
            status_code=400,
        )
    if rule is None:
        rule = OutboundRule()
    rule.name = name.strip() or "Regles sortantes principales"
    rule.prefix = prefix.strip() or None
    rule.emergency_numbers = _normalize_emergency_numbers(emergency_numbers)
    rule.allow_national = allow_national
    rule.allow_mobile = allow_mobile
    rule.allow_international = allow_international
    db.add(rule)
    db.commit()
    return RedirectResponse(_safe_next(next_url, "/outbound"), status_code=303)


def _validate(prefix: str, emergency_numbers: str) -> str | None:
    if not PREFIX_RE.match(prefix.strip()):
        return "Le prefixe de sortie doit contenir 0 a 4 chiffres."
    for number in _split_emergency_numbers(emergency_numbers):
        if not EMERGENCY_RE.match(number):
            return "Les numeros d'urgence doivent contenir 2 a 6 chiffres."
    return None


def _normalize_emergency_numbers(value: str) -> str:
    return ",".join(_split_emergency_numbers(value))


def _split_emergency_numbers(value: str) -> list[str]:
    return [part.strip() for part in value.replace(";", ",").split(",") if part.strip()]


def _safe_next(next_url: str, fallback: str) -> str:
    return next_url if next_url.startswith("/") and not next_url.startswith("//") else fallback
