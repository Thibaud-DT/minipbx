from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import SipTrunk
from app.services.auth import current_admin, has_admin
from app.templating import templates

router = APIRouter(prefix="/trunk")
TRANSPORTS = {"udp", "tcp", "tls"}


def _guard(request: Request, db: Session) -> RedirectResponse | None:
    if not has_admin(db):
        return RedirectResponse("/setup", status_code=303)
    if not current_admin(request, db):
        return RedirectResponse("/login", status_code=303)
    return None


@router.get("", response_class=HTMLResponse)
def trunk_form(request: Request, db: Session = Depends(get_db)):
    guarded = _guard(request, db)
    if guarded:
        return guarded
    trunk = db.scalar(select(SipTrunk).order_by(SipTrunk.id).limit(1))
    return templates.TemplateResponse("trunk/form.html", {"request": request, "trunk": trunk})


@router.post("")
def save_trunk(
    request: Request,
    name: str = Form("Trunk principal"),
    host: str = Form(...),
    username: str = Form(...),
    password: str = Form(""),
    from_user: str = Form(""),
    from_domain: str = Form(""),
    inbound_match: str = Form(""),
    transport: str = Form("udp"),
    enabled: bool = Form(False),
    next_url: str = Form(""),
    db: Session = Depends(get_db),
):
    guarded = _guard(request, db)
    if guarded:
        return guarded
    trunk = db.scalar(select(SipTrunk).order_by(SipTrunk.id).limit(1))
    error = _validate_trunk(host, username, password, inbound_match, transport, trunk_exists=trunk is not None)
    if error:
        return templates.TemplateResponse(
            "trunk/form.html",
            {"request": request, "trunk": trunk, "error": error},
            status_code=400,
        )

    if trunk is None:
        trunk = SipTrunk(
            name=name.strip() or "Trunk principal",
            host=host.strip(),
            username=username.strip(),
            password_secret=password,
            from_user=from_user.strip() or None,
            from_domain=from_domain.strip() or None,
            inbound_match=_normalize_inbound_match(inbound_match) or None,
            transport=transport,
            enabled=enabled,
        )
    else:
        trunk.name = name.strip() or "Trunk principal"
        trunk.host = host.strip()
        trunk.username = username.strip()
        if password:
            trunk.password_secret = password
        trunk.from_user = from_user.strip() or None
        trunk.from_domain = from_domain.strip() or None
        trunk.inbound_match = _normalize_inbound_match(inbound_match) or None
        trunk.transport = transport
        trunk.enabled = enabled
    db.add(trunk)
    db.commit()
    return RedirectResponse(_safe_next(next_url, "/trunk"), status_code=303)


def _validate_trunk(
    host: str,
    username: str,
    password: str,
    inbound_match: str,
    transport: str,
    trunk_exists: bool,
) -> str | None:
    if not host.strip():
        return "Le domaine ou l'adresse IP operateur est obligatoire."
    if not username.strip():
        return "L'identifiant SIP est obligatoire."
    if transport not in TRANSPORTS:
        return "Transport SIP invalide."
    if not trunk_exists and not password:
        return "Le mot de passe SIP est obligatoire a la creation."
    if any(char in inbound_match for char in [";", "#", "[", "]"]):
        return "Les correspondances entrantes ne doivent contenir que des IP, CIDR ou domaines."
    return None


def _normalize_inbound_match(inbound_match: str) -> str:
    matches = []
    for raw_match in inbound_match.replace(",", "\n").splitlines():
        match = raw_match.strip()
        if match and match not in matches:
            matches.append(match)
    return "\n".join(matches)


def _safe_next(next_url: str, fallback: str) -> str:
    return next_url if next_url.startswith("/") and not next_url.startswith("//") else fallback
