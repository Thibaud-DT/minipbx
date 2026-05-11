import logging

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.models import Extension, SipTrunk
from app.security import generate_sip_secret
from app.services.asterisk import apply_revision, generate_config
from app.services.auth import authenticate_admin, create_admin, has_admin, login, logout
from app.services.config_test import run_generated_config_test
from app.services.pbx_settings import save_pbx_settings
from app.templating import templates

router = APIRouter()
logger = logging.getLogger(__name__)
SETUP_WARNING_SESSION_KEY = "setup_warning"


@router.get("/setup", response_class=HTMLResponse)
def setup_form(request: Request, db: Session = Depends(get_db)):
    if has_admin(db):
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse("setup/index.html", {"request": request})


@router.post("/setup")
def setup_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    network_mode: str = Form("host"),
    sip_port: int = Form(5060),
    rtp_start: int = Form(10000),
    rtp_end: int = Form(10100),
    external_address: str = Form(""),
    local_net: str = Form("192.168.1.0/24"),
    first_extension_number: str = Form(""),
    first_extension_name: str = Form("Accueil"),
    first_extension_secret: str = Form(""),
    trunk_name: str = Form(""),
    trunk_host: str = Form(""),
    trunk_username: str = Form(""),
    trunk_password: str = Form(""),
    trunk_from_user: str = Form(""),
    trunk_from_domain: str = Form(""),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    if has_admin(db):
        return RedirectResponse("/login", status_code=303)
    first_extension_number = first_extension_number.strip()
    form = {
        "username": username,
        "network_mode": network_mode,
        "sip_port": str(sip_port),
        "rtp_start": str(rtp_start),
        "rtp_end": str(rtp_end),
        "external_address": external_address,
        "local_net": local_net,
        "first_extension_number": first_extension_number,
        "first_extension_name": first_extension_name,
        "trunk_name": trunk_name,
        "trunk_host": trunk_host,
        "trunk_username": trunk_username,
        "trunk_from_user": trunk_from_user,
        "trunk_from_domain": trunk_from_domain,
    }
    error = _validate_setup(
        password,
        password_confirm,
        network_mode,
        sip_port,
        rtp_start,
        rtp_end,
        first_extension_number,
        first_extension_secret,
        trunk_host,
        trunk_username,
        trunk_password,
    )
    if error:
        return templates.TemplateResponse(
            "setup/index.html",
            {"request": request, "error": error, "form": form},
            status_code=400,
        )
    try:
        admin = create_admin(db, username, password, commit=False)
        save_pbx_settings(
            db,
            network_mode=network_mode,
            sip_port=sip_port,
            rtp_start=rtp_start,
            rtp_end=rtp_end,
            external_address=external_address,
            local_net=local_net,
        )
        first_extension = None
        if first_extension_number.strip():
            first_extension = Extension(
                number=first_extension_number,
                display_name=first_extension_name.strip() or "Accueil",
                sip_username=first_extension_number,
                sip_secret=first_extension_secret.strip() or generate_sip_secret(),
                voicemail_enabled=True,
                voicemail_pin=first_extension_number[-4:].zfill(4),
                outbound_enabled=True,
                inbound_enabled=True,
                enabled=True,
            )
            db.add(first_extension)
        if trunk_host.strip() or trunk_username.strip() or trunk_password.strip():
            db.add(
                SipTrunk(
                    name=trunk_name.strip() or "Trunk principal",
                    host=trunk_host.strip(),
                    username=trunk_username.strip(),
                    password_secret=trunk_password,
                    from_user=trunk_from_user.strip() or None,
                    from_domain=trunk_from_domain.strip() or None,
                    transport="udp",
                    enabled=True,
                )
            )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Initial setup database transaction failed")
        return templates.TemplateResponse(
            "setup/index.html",
            {
                "request": request,
                "error": "Initialisation impossible. Consulte les logs du conteneur pour le detail technique.",
                "form": form,
            },
            status_code=500,
        )

    initial_config_applied = True
    if first_extension:
        db.refresh(first_extension)
        initial_config_applied = _apply_initial_config(db, settings)
        if not initial_config_applied:
            request.session[SETUP_WARNING_SESSION_KEY] = (
                "Le setup est enregistre, mais la configuration Asterisk initiale n'a pas pu etre appliquee. "
                "Va dans Configuration pour previsualiser, corriger si besoin, puis appliquer."
            )
    login(request, admin)
    if first_extension and initial_config_applied:
        return RedirectResponse(f"/extensions/{first_extension.id}/edit", status_code=303)
    return RedirectResponse("/dashboard", status_code=303)


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request, db: Session = Depends(get_db)):
    if not has_admin(db):
        return RedirectResponse("/setup", status_code=303)
    return templates.TemplateResponse("auth/login.html", {"request": request})


@router.post("/login")
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    admin = authenticate_admin(db, username, password)
    if not admin:
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "Identifiants invalides."},
            status_code=401,
        )
    login(request, admin)
    return RedirectResponse("/dashboard", status_code=303)


@router.post("/logout")
def logout_submit(request: Request) -> RedirectResponse:
    logout(request)
    return RedirectResponse("/login", status_code=303)


def _validate_setup(
    password: str,
    password_confirm: str,
    network_mode: str,
    sip_port: int,
    rtp_start: int,
    rtp_end: int,
    first_extension_number: str,
    first_extension_secret: str,
    trunk_host: str,
    trunk_username: str,
    trunk_password: str,
) -> str | None:
    if len(password) < 10 or password != password_confirm:
        return "Le mot de passe doit faire 10 caracteres minimum et etre confirme."
    if network_mode not in {"host", "bridge"}:
        return "Le mode reseau est invalide."
    if sip_port < 1 or sip_port > 65535:
        return "Le port SIP doit etre compris entre 1 et 65535."
    if rtp_start < 1 or rtp_end > 65535 or rtp_start > rtp_end:
        return "La plage RTP est invalide."
    if first_extension_number and (not first_extension_number.isdigit() or not 2 <= len(first_extension_number) <= 6):
        return "La premiere extension doit contenir 2 a 6 chiffres."
    if first_extension_secret and len(first_extension_secret) < 10:
        return "Le mot de passe SIP de la premiere extension doit faire au moins 10 caracteres."
    trunk_fields = [trunk_host.strip(), trunk_username.strip(), trunk_password]
    if any(trunk_fields) and not all(trunk_fields):
        return "Pour configurer un trunk au demarrage, host, identifiant et mot de passe sont obligatoires."
    return None


def _apply_initial_config(db: Session, settings: Settings) -> bool:
    try:
        test_result = run_generated_config_test(db, settings)
        if not test_result.ok:
            return False
        revision = generate_config(db, settings)
        applied = apply_revision(db, revision, settings)
        return applied.status == "applied"
    except Exception:  # noqa: BLE001 - setup must not fail after data has been committed.
        return False
