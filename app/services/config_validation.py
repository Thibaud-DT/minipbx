from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import Settings
from app.models import Extension, InboundRoute, IvrMenu, IvrOption, OutboundRule, RingGroup, RingGroupMember, SipTrunk
from app.services.pbx_settings import get_pbx_settings


@dataclass(frozen=True)
class ConfigIssue:
    level: str
    message: str
    section: str = "general"

    @property
    def blocking(self) -> bool:
        return self.level == "error"


def validate_config(db: Session, settings: Settings) -> list[ConfigIssue]:
    extensions = list(db.scalars(select(Extension).order_by(Extension.number)))
    ring_groups = list(
        db.scalars(
            select(RingGroup)
            .options(selectinload(RingGroup.members).selectinload(RingGroupMember.extension))
            .order_by(RingGroup.number)
        )
    )
    ivr_menus = list(db.scalars(select(IvrMenu).options(selectinload(IvrMenu.options)).order_by(IvrMenu.number)))
    inbound_routes = list(db.scalars(select(InboundRoute).order_by(InboundRoute.id)))
    trunks = list(db.scalars(select(SipTrunk).order_by(SipTrunk.id)))
    outbound_rule = db.scalar(select(OutboundRule).order_by(OutboundRule.id).limit(1))
    pbx_settings = get_pbx_settings(db, settings)

    issues: list[ConfigIssue] = []
    active_extensions = {extension.number: extension for extension in extensions if extension.enabled}
    voicemail_extensions = {extension.number: extension for extension in extensions if extension.enabled and extension.voicemail_enabled}
    active_groups = {group.number: group for group in ring_groups}
    active_ivrs = {menu.number: menu for menu in ivr_menus if menu.enabled}
    enabled_trunks = [trunk for trunk in trunks if trunk.enabled]

    if not active_extensions:
        issues.append(ConfigIssue("warning", "Aucune extension active n'est configuree.", "extensions"))
    if pbx_settings.rtp_start > pbx_settings.rtp_end:
        issues.append(ConfigIssue("error", "La plage RTP est invalide : le port de debut est superieur au port de fin.", "pbx"))
    if pbx_settings.sip_port < 1 or pbx_settings.sip_port > 65535:
        issues.append(ConfigIssue("error", "Le port SIP doit etre compris entre 1 et 65535.", "pbx"))

    if len(enabled_trunks) > 1:
        issues.append(ConfigIssue("warning", "Plusieurs trunks sont actifs ; MiniPBX utilisera le premier trunk actif.", "trunk"))
    for trunk in enabled_trunks:
        if not trunk.host.strip() or not trunk.username.strip() or not trunk.password_secret.strip():
            issues.append(ConfigIssue("error", f"Le trunk '{trunk.name}' est actif mais incomplet.", "trunk"))
    if outbound_rule and not enabled_trunks:
        issues.append(ConfigIssue("warning", "Des regles sortantes existent mais aucun trunk actif n'est configure.", "outbound"))

    _validate_ring_groups(issues, ring_groups, active_extensions, voicemail_extensions)
    _validate_ivrs(issues, ivr_menus, active_extensions, active_groups)
    _validate_inbound_routes(issues, inbound_routes, active_extensions, voicemail_extensions, active_groups, active_ivrs)
    return issues


def has_blocking_issues(issues: list[ConfigIssue]) -> bool:
    return any(issue.blocking for issue in issues)


def group_issues_by_section(issues: list[ConfigIssue]) -> dict[str, list[ConfigIssue]]:
    grouped: dict[str, list[ConfigIssue]] = {}
    for issue in issues:
        grouped.setdefault(issue.section, []).append(issue)
    return grouped


def _validate_ring_groups(
    issues: list[ConfigIssue],
    ring_groups: list[RingGroup],
    active_extensions: dict[str, Extension],
    voicemail_extensions: dict[str, Extension],
) -> None:
    seen_numbers: set[str] = set()
    for group in ring_groups:
        if group.number in seen_numbers:
            issues.append(ConfigIssue("error", f"Le numero de groupe '{group.number}' est duplique.", "groups"))
        seen_numbers.add(group.number)
        active_members = [member for member in group.members if member.extension and member.extension.enabled]
        if not active_members:
            issues.append(ConfigIssue("error", f"Le groupe '{group.number}' ne contient aucune extension active.", "groups"))
        if group.timeout_seconds < 1:
            issues.append(ConfigIssue("error", f"Le timeout du groupe '{group.number}' doit etre superieur a 0 seconde.", "groups"))
        _validate_destination(
            issues,
            label=f"Fallback du groupe {group.number}",
            destination_type=group.fallback_type,
            target=group.fallback_target,
            active_extensions=active_extensions,
            voicemail_extensions=voicemail_extensions,
            active_groups={group.number: group for group in ring_groups},
            active_ivrs={},
            allowed={"hangup", "extension", "voicemail"},
            section="groups",
        )


def _validate_ivrs(
    issues: list[ConfigIssue],
    ivr_menus: list[IvrMenu],
    active_extensions: dict[str, Extension],
    active_groups: dict[str, RingGroup],
) -> None:
    for menu in ivr_menus:
        if not menu.enabled:
            continue
        if menu.timeout_seconds < 1:
            issues.append(ConfigIssue("error", f"Le timeout du standard '{menu.number}' doit etre superieur a 0 seconde.", "ivr"))
        if not menu.options:
            issues.append(ConfigIssue("warning", f"Le standard '{menu.number}' n'a aucune touche configuree.", "ivr"))
        if menu.prompt_mode == "recording" and not menu.prompt_audio_path:
            issues.append(ConfigIssue("warning", f"Le standard '{menu.number}' n'a pas d'enregistrement audio personnalise.", "ivr"))
        if menu.prompt_mode == "tts" and not (menu.prompt_text or "").strip():
            issues.append(ConfigIssue("error", f"Le standard '{menu.number}' est en mode TTS mais le texte est vide.", "ivr"))
        seen_digits: set[str] = set()
        for option in menu.options:
            if option.digit in seen_digits:
                issues.append(ConfigIssue("error", f"Le standard '{menu.number}' contient deux fois la touche {option.digit}.", "ivr"))
            seen_digits.add(option.digit)
            _validate_destination(
                issues,
                label=f"Touche {option.digit} du standard {menu.number}",
                destination_type=option.destination_type,
                target=option.destination_target,
                active_extensions=active_extensions,
                voicemail_extensions={},
                active_groups=active_groups,
                active_ivrs={},
                allowed={"extension", "ring_group"},
                section="ivr",
            )
        _validate_destination(
            issues,
            label=f"Fallback du standard {menu.number}",
            destination_type=menu.fallback_type,
            target=menu.fallback_target,
            active_extensions=active_extensions,
            voicemail_extensions={},
            active_groups=active_groups,
            active_ivrs={},
            allowed={"hangup", "extension", "ring_group"},
            section="ivr",
        )


def _validate_inbound_routes(
    issues: list[ConfigIssue],
    inbound_routes: list[InboundRoute],
    active_extensions: dict[str, Extension],
    voicemail_extensions: dict[str, Extension],
    active_groups: dict[str, RingGroup],
    active_ivrs: dict[str, IvrMenu],
) -> None:
    seen_dids: set[str] = set()
    default_routes = 0
    for route in inbound_routes:
        did = (route.did_number or "").strip()
        if did:
            if did in seen_dids:
                issues.append(ConfigIssue("error", f"Le numero appele '{did}' est utilise par plusieurs routes entrantes.", "inbound"))
            seen_dids.add(did)
        else:
            default_routes += 1
        if route.use_business_hours and route.business_open_time >= route.business_close_time:
            issues.append(ConfigIssue("error", f"Les horaires de la route '{route.name}' sont invalides.", "inbound"))
        _validate_destination(
            issues,
            label=f"Destination ouverte de la route {route.name}",
            destination_type=route.open_destination_type,
            target=route.open_destination_target,
            active_extensions=active_extensions,
            voicemail_extensions=voicemail_extensions,
            active_groups=active_groups,
            active_ivrs=active_ivrs,
            allowed={"hangup", "extension", "ring_group", "ivr", "voicemail"},
            section="inbound",
        )
        _validate_destination(
            issues,
            label=f"Destination fermee de la route {route.name}",
            destination_type=route.closed_destination_type,
            target=route.closed_destination_target,
            active_extensions=active_extensions,
            voicemail_extensions=voicemail_extensions,
            active_groups=active_groups,
            active_ivrs=active_ivrs,
            allowed={"hangup", "extension", "ring_group", "ivr", "voicemail"},
            section="inbound",
        )
    if default_routes > 1:
        issues.append(ConfigIssue("warning", "Plusieurs routes entrantes sans numero appele existent ; la premiere servira de route par defaut.", "inbound"))


def _validate_destination(
    issues: list[ConfigIssue],
    *,
    label: str,
    destination_type: str,
    target: str | None,
    active_extensions: dict[str, Extension],
    voicemail_extensions: dict[str, Extension],
    active_groups: dict[str, RingGroup],
    active_ivrs: dict[str, IvrMenu],
    allowed: set[str],
    section: str,
) -> None:
    if destination_type not in allowed:
        issues.append(ConfigIssue("error", f"{label} : type de destination invalide '{destination_type}'.", section))
        return
    if destination_type == "hangup":
        return
    target = (target or "").strip()
    if not target:
        issues.append(ConfigIssue("error", f"{label} : cible obligatoire.", section))
        return
    if destination_type == "extension" and target not in active_extensions:
        issues.append(ConfigIssue("error", f"{label} : extension active introuvable ({target}).", section))
    if destination_type == "voicemail" and target not in voicemail_extensions:
        issues.append(ConfigIssue("error", f"{label} : messagerie active introuvable ({target}).", section))
    if destination_type == "ring_group" and target not in active_groups:
        issues.append(ConfigIssue("error", f"{label} : groupe d'appel introuvable ({target}).", section))
    if destination_type == "ivr" and target not in active_ivrs:
        issues.append(ConfigIssue("error", f"{label} : standard actif introuvable ({target}).", section))
