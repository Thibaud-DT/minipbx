import shutil
import shlex
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import Settings
from app.models import ConfigRevision, Extension, InboundRoute, IvrMenu, IvrOption, OutboundRule, RingGroup, RingGroupMember, SipTrunk
from app.services.pbx_settings import get_pbx_settings


GENERATED_FILES = {
    "pjsip_minipbx.conf": "asterisk/pjsip_minipbx.conf.j2",
    "extensions_minipbx.conf": "asterisk/extensions_minipbx.conf.j2",
    "voicemail_minipbx.conf": "asterisk/voicemail_minipbx.conf.j2",
    "manager_minipbx.conf": "asterisk/manager_minipbx.conf.j2",
    "rtp.conf": "asterisk/rtp.conf.j2",
}


@dataclass(frozen=True)
class AsteriskStatus:
    running: bool
    message: str


def _jinja_env() -> Environment:
    template_dir = Path(__file__).resolve().parents[1] / "templates"
    return Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(enabled_extensions=("html", "xml")),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_configs(db: Session, settings: Settings) -> dict[str, str]:
    extensions = list(db.scalars(select(Extension).order_by(Extension.number)))
    ring_groups = list(
        db.scalars(
            select(RingGroup)
            .options(selectinload(RingGroup.members).selectinload(RingGroupMember.extension))
            .order_by(RingGroup.number)
        )
    )
    inbound_routes = list(db.scalars(select(InboundRoute).order_by(InboundRoute.id)))
    inbound_route = inbound_routes[0] if inbound_routes else None
    ivr_menus = list(
        db.scalars(
            select(IvrMenu)
            .options(selectinload(IvrMenu.options))
            .order_by(IvrMenu.number)
        )
    )
    outbound_rule = db.scalar(select(OutboundRule).order_by(OutboundRule.id).limit(1))
    trunk = db.scalar(select(SipTrunk).where(SipTrunk.enabled.is_(True)).limit(1))
    pbx_settings = get_pbx_settings(db, settings)
    emergency_numbers = ["15", "17", "18", "112"]
    if outbound_rule:
        emergency_numbers = [number.strip() for number in outbound_rule.emergency_numbers.split(",") if number.strip()]
    env = _jinja_env()
    context = {
        "extensions": extensions,
        "extensions_by_number": {extension.number: extension for extension in extensions},
        "ring_groups": ring_groups,
        "inbound_route": inbound_route,
        "inbound_routes": _inbound_route_entries(inbound_routes),
        "ivr_menus": ivr_menus,
        "outbound_rule": outbound_rule,
        "emergency_numbers": emergency_numbers,
        "trunk": trunk,
        "trunk_inbound_matches": _trunk_inbound_matches(trunk),
        "sip_port": pbx_settings.sip_port,
        "rtp_start": pbx_settings.rtp_start,
        "rtp_end": pbx_settings.rtp_end,
        "external_address": pbx_settings.external_address,
        "local_net": pbx_settings.local_net,
        "ami_enabled": settings.ami_enabled,
        "ami_bind_address": settings.ami_bind_address,
        "ami_port": settings.ami_port,
        "ami_username": settings.ami_username,
        "ami_password": settings.ami_password,
        "tts_backend": settings.tts_backend,
    }
    return {filename: env.get_template(template).render(**context) for filename, template in GENERATED_FILES.items()}


def _trunk_inbound_matches(trunk: SipTrunk | None) -> list[str]:
    if not trunk:
        return []
    raw_matches = trunk.inbound_match or trunk.host
    matches = []
    for raw_match in raw_matches.replace(",", "\n").splitlines():
        match = raw_match.strip()
        if match and match not in matches:
            matches.append(match)
    return matches


def generate_config(db: Session, settings: Settings) -> ConfigRevision:
    generated = render_configs(db, settings)
    revision_dir = _unique_timestamped_dir(settings.generated_config_dir)
    revision_dir.mkdir(parents=True, exist_ok=True)
    for filename, content in generated.items():
        if not content.strip():
            raise ValueError(f"Generated {filename} is empty")
        (revision_dir / filename).write_text(content, encoding="utf-8")

    revision = ConfigRevision(
        status="generated",
        summary=f"{len(generated)} fichiers generes",
        generated_path=str(revision_dir),
    )
    db.add(revision)
    db.commit()
    db.refresh(revision)
    return revision


def _asterisk_business_days(days: str | None) -> str:
    selected = [day.strip() for day in (days or "").split(",") if day.strip()]
    valid = [day for day in selected if day in {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}]
    if valid == ["mon", "tue", "wed", "thu", "fri"]:
        return "mon-fri"
    if valid == ["sat", "sun"]:
        return "sat-sun"
    return "&".join(valid) if valid else "mon-fri"


def _asterisk_holiday_dates(value: str | None) -> list[dict[str, str]]:
    dates = []
    for raw_date in (value or "").replace(",", "\n").splitlines():
        raw_date = raw_date.strip()
        try:
            parsed = datetime.strptime(raw_date, "%Y-%m-%d")
        except ValueError:
            continue
        dates.append({"day": str(parsed.day), "month": parsed.strftime("%b").lower()})
    return dates


def _inbound_route_entries(routes: list[InboundRoute]) -> list[dict]:
    default_route = next((route for route in routes if not route.did_number), routes[0] if routes else None)
    return [
        {
            "route": route,
            "is_default": route == default_route,
            "business_days": _asterisk_business_days(route.business_days),
            "holiday_dates": _asterisk_holiday_dates(route.holiday_dates),
        }
        for route in routes
    ]


def apply_revision(
    db: Session,
    revision: ConfigRevision,
    settings: Settings,
    *,
    reload_asterisk: bool = True,
) -> ConfigRevision:
    source_dir = Path(revision.generated_path)
    missing_files = [filename for filename in GENERATED_FILES if not (source_dir / filename).is_file()]
    if missing_files:
        revision.status = "invalid"
        revision.summary = f"Revision incomplete, fichiers manquants: {', '.join(missing_files)}"
        db.add(revision)
        db.commit()
        db.refresh(revision)
        return revision

    backup_dir = _unique_timestamped_dir(settings.backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    settings.asterisk_config_dir.mkdir(parents=True, exist_ok=True)

    original_files: dict[str, Path | None] = {}
    for filename in GENERATED_FILES:
        target = settings.asterisk_config_dir / filename
        if target.exists():
            shutil.copy2(target, backup_dir / filename)
            original_files[filename] = backup_dir / filename
        else:
            original_files[filename] = None
        shutil.copy2(source_dir / filename, target)

    if settings.asterisk_apply_enabled and reload_asterisk:
        try:
            run_command(settings.asterisk_reload_command)
        except (OSError, subprocess.CalledProcessError) as exc:
            _restore_files(settings.asterisk_config_dir, original_files)
            revision.status = "reload_failed"
            revision.summary = f"Reload Asterisk en echec, ancienne configuration restauree: {_command_error(exc)}"
            db.add(revision)
            db.commit()
            db.refresh(revision)
            return revision

    revision.status = "applied"
    if settings.asterisk_apply_enabled and not reload_asterisk:
        revision.summary = f"Configuration ecrite avant demarrage Asterisk, sauvegarde: {backup_dir}"
    else:
        revision.summary = f"Configuration appliquee, sauvegarde: {backup_dir}"
    db.add(revision)
    db.commit()
    db.refresh(revision)
    return revision


def _command_error(exc: OSError | subprocess.CalledProcessError) -> str:
    if isinstance(exc, subprocess.CalledProcessError):
        output = "\n".join(part for part in [exc.stderr, exc.stdout] if part).strip()
        return output or f"code retour {exc.returncode}"
    return str(exc)


def run_command(command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(shlex.split(command), check=True, capture_output=True, text=True)


def get_asterisk_status(settings: Settings) -> AsteriskStatus:
    if not settings.asterisk_apply_enabled:
        return AsteriskStatus(running=False, message="Asterisk non controle dans ce mode")
    try:
        result = run_command(settings.asterisk_status_command)
    except (OSError, subprocess.CalledProcessError) as exc:
        return AsteriskStatus(running=False, message=str(exc))
    return AsteriskStatus(running=True, message=result.stdout.strip() or "Asterisk repond")


def _restore_files(target_dir: Path, original_files: dict[str, Path | None]) -> None:
    for filename, backup_path in original_files.items():
        target = target_dir / filename
        if backup_path is None:
            target.unlink(missing_ok=True)
        elif backup_path.exists():
            shutil.copy2(backup_path, target)


def _unique_timestamped_dir(root: Path) -> Path:
    base = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    candidate = root / base
    suffix = 1
    while candidate.exists():
        candidate = root / f"{base}-{suffix}"
        suffix += 1
    return candidate
