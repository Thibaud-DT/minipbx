import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.models import Extension
from app.security import generate_sip_secret
from app.services.asterisk import apply_revision, generate_config
from app.services.auth import current_admin, has_admin
from app.services.config_test import run_generated_config_test
from app.services.prompts import AUDIO_EXTENSIONS, PromptFileError, save_prompt_file
from app.templating import templates

router = APIRouter(prefix="/extensions")
EXTENSION_RE = re.compile(r"^\d{2,6}$")
GREETING_MODES = {"default", "recording", "tts"}


def _guard(request: Request, db: Session) -> RedirectResponse | None:
    if not has_admin(db):
        return RedirectResponse("/setup", status_code=303)
    if not current_admin(request, db):
        return RedirectResponse("/login", status_code=303)
    return None


@router.get("", response_class=HTMLResponse)
def list_extensions(request: Request, db: Session = Depends(get_db)):
    guarded = _guard(request, db)
    if guarded:
        return guarded
    extensions = list(db.scalars(select(Extension).order_by(Extension.number)))
    return templates.TemplateResponse("extensions/list.html", {"request": request, "extensions": extensions})


@router.get("/{extension_id}/edit", response_class=HTMLResponse)
def edit_extension_form(
    extension_id: int,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    guarded = _guard(request, db)
    if guarded:
        return guarded
    extension = db.get(Extension, extension_id)
    if not extension:
        return RedirectResponse("/extensions", status_code=303)
    return _render_edit(request, extension, settings)


@router.post("")
def create_extension(
    request: Request,
    number: str = Form(...),
    display_name: str = Form(...),
    email: str = Form(""),
    voicemail_enabled: bool = Form(False),
    outbound_enabled: bool = Form(False),
    next_url: str = Form(""),
    db: Session = Depends(get_db),
):
    guarded = _guard(request, db)
    if guarded:
        return guarded
    error = _validate_extension(db, number)
    if error:
        extensions = list(db.scalars(select(Extension).order_by(Extension.number)))
        return templates.TemplateResponse(
            "extensions/list.html",
            {"request": request, "extensions": extensions, "error": error},
            status_code=400,
        )
    extension = Extension(
        number=number,
        display_name=display_name.strip(),
        sip_username=number,
        sip_secret=generate_sip_secret(),
        email=email.strip() or None,
        voicemail_enabled=voicemail_enabled,
        outbound_enabled=outbound_enabled,
        voicemail_pin=number[-4:].zfill(4),
    )
    db.add(extension)
    db.commit()
    return RedirectResponse(_safe_next(next_url, "/extensions"), status_code=303)


@router.post("/{extension_id}")
async def update_extension(
    extension_id: int,
    request: Request,
    number: str = Form(...),
    display_name: str = Form(...),
    email: str = Form(""),
    voicemail_pin: str = Form(...),
    voicemail_enabled: bool = Form(False),
    outbound_enabled: bool = Form(False),
    inbound_enabled: bool = Form(False),
    enabled: bool = Form(False),
    voicemail_greeting_mode: str = Form("default"),
    voicemail_greeting_text: str = Form(""),
    voicemail_greeting_file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    guarded = _guard(request, db)
    if guarded:
        return guarded
    extension = db.get(Extension, extension_id)
    if not extension:
        return RedirectResponse("/extensions", status_code=303)
    error = _validate_extension(db, number, extension_id=extension.id)
    if error:
        return templates.TemplateResponse(
            "extensions/edit.html",
            _edit_context(request, extension, settings, error),
            status_code=400,
        )
    if not voicemail_pin.isdigit() or not 4 <= len(voicemail_pin) <= 8:
        return templates.TemplateResponse(
            "extensions/edit.html",
            _edit_context(request, extension, settings, "Le PIN de messagerie doit contenir 4 a 8 chiffres."),
            status_code=400,
        )
    greeting_error = _validate_greeting(voicemail_greeting_mode, voicemail_greeting_text, voicemail_greeting_file, settings, extension)
    if greeting_error:
        return templates.TemplateResponse(
            "extensions/edit.html",
            _edit_context(request, extension, settings, greeting_error),
            status_code=400,
        )

    if voicemail_greeting_mode == "recording" and voicemail_greeting_file and voicemail_greeting_file.filename:
        try:
            extension.voicemail_greeting_audio_path = str(await save_prompt_file(voicemail_greeting_file, settings.prompt_dir, "voicemail"))
        except PromptFileError as exc:
            return templates.TemplateResponse(
                "extensions/edit.html",
                _edit_context(request, extension, settings, _prompt_error_label(exc.code)),
                status_code=400,
            )

    extension.number = number
    extension.display_name = display_name.strip()
    extension.sip_username = number
    extension.email = email.strip() or None
    extension.voicemail_pin = voicemail_pin
    extension.voicemail_enabled = voicemail_enabled
    extension.outbound_enabled = outbound_enabled
    extension.inbound_enabled = inbound_enabled
    extension.enabled = enabled
    extension.voicemail_greeting_mode = voicemail_greeting_mode
    extension.voicemail_greeting_text = voicemail_greeting_text.strip() or None
    if voicemail_greeting_mode != "recording":
        extension.voicemail_greeting_audio_path = None
    db.add(extension)
    db.commit()
    return RedirectResponse("/extensions", status_code=303)


@router.post("/{extension_id}/regenerate-secret")
def regenerate_extension_secret(
    extension_id: int,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    guarded = _guard(request, db)
    if guarded:
        return guarded
    extension = db.get(Extension, extension_id)
    if extension:
        extension.sip_secret = generate_sip_secret()
        db.add(extension)
        db.commit()
        if run_generated_config_test(db, settings).ok:
            revision = generate_config(db, settings)
            apply_revision(db, revision, settings)
    return RedirectResponse(f"/extensions/{extension_id}/edit", status_code=303)


@router.post("/{extension_id}/delete")
def delete_extension(
    extension_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    guarded = _guard(request, db)
    if guarded:
        return guarded
    extension = db.get(Extension, extension_id)
    if extension:
        db.delete(extension)
        db.commit()
    return RedirectResponse("/extensions", status_code=303)


def _validate_extension(db: Session, number: str, extension_id: int | None = None) -> str | None:
    if not EXTENSION_RE.match(number):
        return "Le numero doit contenir 2 a 6 chiffres."
    query = select(Extension.id).where(Extension.number == number)
    if extension_id is not None:
        query = query.where(Extension.id != extension_id)
    exists = db.scalar(query)
    if exists:
        return "Ce numero existe deja."
    return None


def _validate_greeting(
    mode: str,
    text: str,
    upload: UploadFile | None,
    settings: Settings,
    extension: Extension,
) -> str | None:
    if mode not in GREETING_MODES:
        return "Le type de message de messagerie est invalide."
    if mode == "tts" and settings.tts_backend == "none":
        return "Le TTS n'est pas active sur cette installation."
    if mode == "tts" and not text.strip():
        return "Le texte TTS du message de messagerie est obligatoire."
    if mode == "recording" and not extension.voicemail_greeting_audio_path and not (upload and upload.filename):
        return "Un fichier audio est obligatoire pour ce message de messagerie."
    if mode == "recording" and upload and upload.filename and Path(upload.filename).suffix.lower() not in AUDIO_EXTENSIONS:
        return "Le fichier audio doit etre au format wav, gsm, sln, ulaw ou alaw."
    return None


def _prompt_error_label(code: str) -> str:
    return {
        "fichier-audio-trop-volumineux": "Le fichier audio est trop volumineux.",
        "fichier-audio-invalide": "Le fichier audio n'est pas lisible ou n'est pas un WAV PCM compatible.",
    }.get(code, "Le fichier audio est invalide.")


def _render_edit(request: Request, extension: Extension, settings: Settings, error: str | None = None) -> HTMLResponse:
    return templates.TemplateResponse("extensions/edit.html", _edit_context(request, extension, settings, error))


def _edit_context(request: Request, extension: Extension, settings: Settings, error: str | None = None) -> dict:
    return {
        "request": request,
        "extension": extension,
        "error": error,
        "tts_backend": settings.tts_backend,
    }


def _safe_next(next_url: str, fallback: str) -> str:
    return next_url if next_url.startswith("/") and not next_url.startswith("//") else fallback
