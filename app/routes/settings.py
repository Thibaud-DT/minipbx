from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import Settings, get_settings
from app.database import get_db
from app.models import ConfigRevision, Extension, InboundRoute, IvrMenu, IvrOption, OutboundRule, PbxSettings, RingGroup, RingGroupMember, SipTrunk
from app.services.asterisk import GENERATED_FILES, render_configs
from app.services.auth import current_admin, has_admin
from app.services.config_validation import group_issues_by_section, validate_config
from app.services.pbx_settings import get_pbx_settings, save_pbx_settings
from app.templating import templates

router = APIRouter(prefix="/settings")

SETTINGS_TABS = {
    "pbx": "PBX",
    "extensions": "Extensions",
    "groups": "Groupes",
    "ivr": "Standard",
    "inbound": "Entrant",
    "outbound": "Sortant",
    "trunk": "Trunk SIP",
    "asterisk": "Asterisk",
}
BUSINESS_DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
BUSINESS_DAY_LABELS = {
    "mon": "Lundi",
    "tue": "Mardi",
    "wed": "Mercredi",
    "thu": "Jeudi",
    "fri": "Vendredi",
    "sat": "Samedi",
    "sun": "Dimanche",
}


def _guard(request: Request, db: Session) -> RedirectResponse | None:
    if not has_admin(db):
        return RedirectResponse("/setup", status_code=303)
    if not current_admin(request, db):
        return RedirectResponse("/login", status_code=303)
    return None


@router.get("", response_class=HTMLResponse)
def settings_page(
    request: Request,
    tab: str = "pbx",
    selected: str = "pjsip_minipbx.conf",
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    guarded = _guard(request, db)
    if guarded:
        return guarded
    if tab not in SETTINGS_TABS:
        tab = "pbx"

    extensions = list(db.scalars(select(Extension).order_by(Extension.number)))
    active_extensions = [extension for extension in extensions if extension.enabled]
    ring_groups = list(
        db.scalars(
            select(RingGroup)
            .options(selectinload(RingGroup.members).selectinload(RingGroupMember.extension))
            .order_by(RingGroup.number)
        )
    )
    ivr_menus = list(
        db.scalars(
            select(IvrMenu)
            .options(selectinload(IvrMenu.options))
            .order_by(IvrMenu.number)
        )
    )
    inbound_routes = list(db.scalars(select(InboundRoute).order_by(InboundRoute.did_number.is_(None).desc(), InboundRoute.did_number, InboundRoute.id)))
    inbound_route = inbound_routes[0] if inbound_routes else None
    outbound_rule = db.scalar(select(OutboundRule).order_by(OutboundRule.id).limit(1))
    trunk = db.scalar(select(SipTrunk).order_by(SipTrunk.id).limit(1))
    active_trunk = db.scalar(select(SipTrunk).where(SipTrunk.enabled.is_(True)).limit(1))
    pbx_settings = get_pbx_settings(db, settings)

    configs = render_configs(db, settings)
    validation_issues = validate_config(db, settings)
    issues_by_section = group_issues_by_section(validation_issues)
    if selected not in configs:
        selected = "pjsip_minipbx.conf"
    last_revision = db.scalar(select(ConfigRevision).order_by(ConfigRevision.created_at.desc()).limit(1))
    generated_files = []
    if last_revision:
        revision_dir = Path(last_revision.generated_path)
        generated_files = [filename for filename in GENERATED_FILES if (revision_dir / filename).exists()]

    return templates.TemplateResponse(
        "settings/index.html",
        {
            "request": request,
            "tabs": SETTINGS_TABS,
            "tab": tab,
            "next_url": f"/settings?tab={tab}",
            "pbx_settings": pbx_settings,
            "extensions": extensions,
            "active_extensions": active_extensions,
            "ring_groups": ring_groups,
            "ivr_menus": ivr_menus,
            "route": inbound_route,
            "inbound_routes": inbound_routes,
            "rule": outbound_rule,
            "trunk": trunk,
            "active_trunk": active_trunk,
            "business_days": BUSINESS_DAYS,
            "business_day_labels": BUSINESS_DAY_LABELS,
            "tts_backend": settings.tts_backend,
            "configs": configs,
            "selected": selected,
            "content": configs[selected],
            "validation_issues": validation_issues,
            "issues_by_section": issues_by_section,
            "last_revision": last_revision,
            "generated_files": generated_files,
        },
    )


@router.post("/pbx")
def save_pbx_settings_route(
    request: Request,
    network_mode: str = Form("host"),
    sip_port: int = Form(5060),
    rtp_start: int = Form(10000),
    rtp_end: int = Form(10100),
    external_address: str = Form(""),
    local_net: str = Form(""),
    db: Session = Depends(get_db),
):
    guarded = _guard(request, db)
    if guarded:
        return guarded
    error = _validate_pbx_settings(network_mode, sip_port, rtp_start, rtp_end, local_net)
    if error:
        return RedirectResponse(f"/settings?tab=pbx&error={error}", status_code=303)
    save_pbx_settings(
        db,
        network_mode=network_mode,
        sip_port=sip_port,
        rtp_start=rtp_start,
        rtp_end=rtp_end,
        external_address=external_address,
        local_net=local_net,
    )
    db.commit()
    return RedirectResponse("/settings?tab=pbx", status_code=303)


def _validate_pbx_settings(network_mode: str, sip_port: int, rtp_start: int, rtp_end: int, local_net: str) -> str | None:
    if network_mode not in {"host", "bridge"}:
        return "mode-reseau-invalide"
    if sip_port < 1 or sip_port > 65535:
        return "port-sip-invalide"
    if rtp_start < 1 or rtp_end > 65535 or rtp_start > rtp_end:
        return "plage-rtp-invalide"
    if not local_net.strip():
        return "reseau-local-obligatoire"
    return None
