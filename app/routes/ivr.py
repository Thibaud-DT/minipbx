import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import Settings, get_settings
from app.database import get_db
from app.models import Extension, IvrMenu, IvrOption, RingGroup
from app.services.auth import current_admin, has_admin
from app.services.prompts import AUDIO_EXTENSIONS, PromptFileError, save_prompt_file
from app.templating import templates

router = APIRouter(prefix="/ivr")
NUMBER_RE = re.compile(r"^\d{2,6}$")
DIGITS = {str(number) for number in range(10)}
PROMPT_MODES = {"recording", "tts"}
DESTINATION_TYPES = {"extension", "ring_group"}
FALLBACK_TYPES = {"hangup", "extension", "ring_group"}
def _guard(request: Request, db: Session) -> RedirectResponse | None:
    if not has_admin(db):
        return RedirectResponse("/setup", status_code=303)
    if not current_admin(request, db):
        return RedirectResponse("/login", status_code=303)
    return None


@router.get("/{menu_id}/edit", response_class=HTMLResponse)
def edit_ivr_menu_form(
    menu_id: int,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    guarded = _guard(request, db)
    if guarded:
        return guarded
    menu = _get_menu(db, menu_id)
    if not menu:
        return RedirectResponse("/settings?tab=ivr", status_code=303)
    return templates.TemplateResponse(
        "ivr/edit.html",
        _edit_context(request, db, settings, menu),
    )


@router.post("")
async def create_ivr_menu(
    request: Request,
    name: str = Form(...),
    number: str = Form(...),
    prompt_mode: str = Form("recording"),
    prompt_text: str = Form(""),
    timeout_seconds: int = Form(8),
    fallback_type: str = Form("hangup"),
    fallback_target: str = Form(""),
    enabled: bool = Form(False),
    option_digits: list[str] = Form([]),
    option_destination_types: list[str] = Form([]),
    option_destination_targets: list[str] = Form([]),
    prompt_file: UploadFile | None = File(None),
    next_url: str = Form(""),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    guarded = _guard(request, db)
    if guarded:
        return guarded

    options = _build_options(option_digits, option_destination_types, option_destination_targets)
    error = _validate_menu(
        db=db,
        number=number,
        prompt_mode=prompt_mode,
        prompt_text=prompt_text,
        prompt_file=prompt_file,
        tts_backend=settings.tts_backend,
        timeout_seconds=timeout_seconds,
        fallback_type=fallback_type,
        fallback_target=fallback_target,
        options=options,
    )
    if error:
        return RedirectResponse(f"/settings?tab=ivr&error={error}", status_code=303)

    audio_path = None
    if prompt_mode == "recording" and prompt_file and prompt_file.filename:
        try:
            audio_path = await save_prompt_file(prompt_file, settings.prompt_dir, "ivr")
        except PromptFileError as exc:
            return RedirectResponse(f"/settings?tab=ivr&error={exc.code}", status_code=303)

    menu = IvrMenu(
        name=name.strip(),
        number=number.strip(),
        prompt_mode=prompt_mode,
        prompt_text=prompt_text.strip() or None,
        prompt_audio_path=str(audio_path) if audio_path else None,
        timeout_seconds=timeout_seconds,
        fallback_type=fallback_type,
        fallback_target=fallback_target.strip() or None,
        enabled=enabled,
    )
    menu.options = [
        IvrOption(digit=digit, destination_type=destination_type, destination_target=target)
        for digit, destination_type, target in options
    ]
    db.add(menu)
    db.commit()
    return RedirectResponse(_safe_next(next_url, "/settings?tab=ivr"), status_code=303)


@router.post("/{menu_id}")
async def update_ivr_menu(
    menu_id: int,
    request: Request,
    name: str = Form(...),
    number: str = Form(...),
    prompt_mode: str = Form("recording"),
    prompt_text: str = Form(""),
    timeout_seconds: int = Form(8),
    fallback_type: str = Form("hangup"),
    fallback_target: str = Form(""),
    enabled: bool = Form(False),
    option_digits: list[str] = Form([]),
    option_destination_types: list[str] = Form([]),
    option_destination_targets: list[str] = Form([]),
    prompt_file: UploadFile | None = File(None),
    next_url: str = Form(""),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    guarded = _guard(request, db)
    if guarded:
        return guarded
    menu = _get_menu(db, menu_id)
    if not menu:
        return RedirectResponse(_safe_next(next_url, "/settings?tab=ivr"), status_code=303)

    options = _build_options(option_digits, option_destination_types, option_destination_targets)
    error = _validate_menu(
        db=db,
        number=number,
        prompt_mode=prompt_mode,
        prompt_text=prompt_text,
        prompt_file=prompt_file,
        tts_backend=settings.tts_backend,
        timeout_seconds=timeout_seconds,
        fallback_type=fallback_type,
        fallback_target=fallback_target,
        options=options,
        current_menu_id=menu.id,
        existing_audio_path=menu.prompt_audio_path,
    )
    if error:
        return templates.TemplateResponse(
            "ivr/edit.html",
            _edit_context(request, db, settings, menu, error=error),
            status_code=400,
        )

    if prompt_mode == "recording" and prompt_file and prompt_file.filename:
        try:
            menu.prompt_audio_path = str(await save_prompt_file(prompt_file, settings.prompt_dir, "ivr"))
        except PromptFileError as exc:
            return templates.TemplateResponse(
                "ivr/edit.html",
                _edit_context(request, db, settings, menu, error=exc.code),
                status_code=400,
            )

    menu.name = name.strip()
    menu.number = number.strip()
    menu.prompt_mode = prompt_mode
    menu.prompt_text = prompt_text.strip() or None
    menu.timeout_seconds = timeout_seconds
    menu.fallback_type = fallback_type
    menu.fallback_target = fallback_target.strip() or None
    menu.enabled = enabled
    menu.options = [
        IvrOption(digit=digit, destination_type=destination_type, destination_target=target)
        for digit, destination_type, target in options
    ]
    db.add(menu)
    db.commit()
    return RedirectResponse(_safe_next(next_url, "/settings?tab=ivr"), status_code=303)


@router.post("/{menu_id}/delete")
def delete_ivr_menu(
    menu_id: int,
    request: Request,
    next_url: str = Form(""),
    db: Session = Depends(get_db),
):
    guarded = _guard(request, db)
    if guarded:
        return guarded
    menu = db.get(IvrMenu, menu_id)
    if menu:
        db.delete(menu)
        db.commit()
    return RedirectResponse(_safe_next(next_url, "/settings?tab=ivr"), status_code=303)


def _build_options(
    digits: list[str],
    destination_types: list[str],
    targets: list[str],
) -> list[tuple[str, str, str]]:
    options = []
    for digit, destination_type, target in zip(digits, destination_types, targets, strict=False):
        digit = digit.strip()
        destination_type = destination_type.strip()
        target = target.strip()
        if digit or target:
            options.append((digit, destination_type, target))
    return options


def _get_menu(db: Session, menu_id: int) -> IvrMenu | None:
    return db.scalar(
        select(IvrMenu)
        .options(selectinload(IvrMenu.options))
        .where(IvrMenu.id == menu_id)
    )


def _edit_context(
    request: Request,
    db: Session,
    settings: Settings,
    menu: IvrMenu,
    error: str | None = None,
) -> dict:
    return {
        "request": request,
        "menu": menu,
        "active_extensions": list(db.scalars(select(Extension).where(Extension.enabled.is_(True)).order_by(Extension.number))),
        "ring_groups": list(db.scalars(select(RingGroup).order_by(RingGroup.number))),
        "tts_backend": settings.tts_backend,
        "error": error,
        "error_label": _error_label(error) if error else None,
    }


def _error_label(error: str | None) -> str:
    labels = {
        "numero-standard-invalide": "Le numero du standard doit contenir 2 a 6 chiffres.",
        "numero-deja-utilise": "Ce numero est deja utilise.",
        "message-invalide": "Le type de message est invalide.",
        "tts-indisponible": "Le TTS n'est pas active sur cette installation.",
        "texte-tts-obligatoire": "Le texte TTS est obligatoire.",
        "enregistrement-obligatoire": "Un fichier audio est obligatoire en mode enregistrement.",
        "format-audio-invalide": "Le fichier audio doit etre au format wav, gsm, sln, ulaw ou alaw.",
        "fichier-audio-invalide": "Le fichier audio n'est pas lisible ou n'est pas un WAV PCM compatible.",
        "timeout-invalide": "Le delai doit etre compris entre 3 et 30 secondes.",
        "secours-invalide": "La destination de secours est invalide.",
        "cible-secours-obligatoire": "La cible de secours est obligatoire.",
        "cible-secours-inconnue": "La cible de secours est inconnue.",
        "option-obligatoire": "Au moins une touche doit etre configuree.",
        "touche-invalide": "La touche doit etre un chiffre.",
        "touche-dupliquee": "Une touche est configuree plusieurs fois.",
        "destination-invalide": "La destination de touche est invalide.",
        "cible-obligatoire": "Choisissez une cible pour la touche.",
        "cible-inconnue": "La cible choisie est inconnue.",
        "fichier-audio-trop-volumineux": "Le fichier audio est trop volumineux.",
    }
    return labels.get(error or "", error or "Erreur inconnue.")


def _validate_menu(
    db: Session,
    number: str,
    prompt_mode: str,
    prompt_text: str,
    prompt_file: UploadFile | None,
    tts_backend: str,
    timeout_seconds: int,
    fallback_type: str,
    fallback_target: str,
    options: list[tuple[str, str, str]],
    current_menu_id: int | None = None,
    existing_audio_path: str | None = None,
) -> str | None:
    number = number.strip()
    if not NUMBER_RE.match(number):
        return "numero-standard-invalide"
    if db.scalar(select(Extension.id).where(Extension.number == number)):
        return "numero-deja-utilise"
    if db.scalar(select(RingGroup.id).where(RingGroup.number == number)):
        return "numero-deja-utilise"
    menu_query = select(IvrMenu.id).where(IvrMenu.number == number)
    if current_menu_id:
        menu_query = menu_query.where(IvrMenu.id != current_menu_id)
    if db.scalar(menu_query):
        return "numero-deja-utilise"
    if prompt_mode not in PROMPT_MODES:
        return "message-invalide"
    if prompt_mode == "tts" and tts_backend == "none":
        return "tts-indisponible"
    if prompt_mode == "tts" and not prompt_text.strip():
        return "texte-tts-obligatoire"
    if prompt_mode == "recording" and not existing_audio_path and not (prompt_file and prompt_file.filename):
        return "enregistrement-obligatoire"
    if prompt_mode == "recording" and prompt_file and Path(prompt_file.filename).suffix.lower() not in AUDIO_EXTENSIONS:
        return "format-audio-invalide"
    if timeout_seconds < 3 or timeout_seconds > 30:
        return "timeout-invalide"
    if fallback_type not in FALLBACK_TYPES:
        return "secours-invalide"
    if fallback_type != "hangup" and not fallback_target.strip():
        return "cible-secours-obligatoire"
    if fallback_type != "hangup" and not _target_exists(db, fallback_type, fallback_target):
        return "cible-secours-inconnue"
    if not options:
        return "option-obligatoire"
    seen_digits = set()
    for digit, destination_type, target in options:
        if digit not in DIGITS:
            return "touche-invalide"
        if digit in seen_digits:
            return "touche-dupliquee"
        if destination_type not in DESTINATION_TYPES:
            return "destination-invalide"
        if not target:
            return "cible-obligatoire"
        if not _target_exists(db, destination_type, target):
            return "cible-inconnue"
        seen_digits.add(digit)
    return None


def _target_exists(db: Session, destination_type: str, target: str) -> bool:
    if destination_type == "extension":
        return bool(db.scalar(select(Extension.id).where(Extension.number == target)))
    if destination_type == "ring_group":
        return bool(db.scalar(select(RingGroup.id).where(RingGroup.number == target)))
    return False


def _safe_next(next_url: str, fallback: str) -> str:
    return next_url if next_url.startswith("/") and not next_url.startswith("//") else fallback
