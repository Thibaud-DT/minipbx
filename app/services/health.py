from dataclasses import dataclass

from app.config import Settings
from app.services.asterisk import get_asterisk_status
from app.services.diagnostics import _run_asterisk_rx
from app.services.monitoring import parse_channels, parse_contacts, parse_registrations


@dataclass(frozen=True)
class HealthSummary:
    asterisk_running: bool
    asterisk_message: str
    version: str
    uptime: str
    endpoints_ok: bool
    contacts_count: int
    active_calls_count: int
    trunk_registered: bool
    recent_errors: str


def collect_health(settings: Settings) -> HealthSummary:
    status = get_asterisk_status(settings)
    if not settings.asterisk_apply_enabled:
        return HealthSummary(
            asterisk_running=False,
            asterisk_message=status.message,
            version="-",
            uptime="-",
            endpoints_ok=False,
            contacts_count=0,
            active_calls_count=0,
            trunk_registered=False,
            recent_errors="Asterisk non controle dans ce mode.",
        )

    version = _run_asterisk_rx("Version", "core show version")
    uptime = _run_asterisk_rx("Uptime", "core show uptime")
    endpoints = _run_asterisk_rx("Endpoints", "pjsip show endpoints")
    contacts = parse_contacts(_run_asterisk_rx("Contacts", "pjsip show contacts").output)
    channels = parse_channels(_run_asterisk_rx("Channels", "core show channels concise").output)
    registrations = parse_registrations(_run_asterisk_rx("Registrations", "pjsip show registrations").output)
    errors = _run_asterisk_rx("Logs", "logger show channels")

    return HealthSummary(
        asterisk_running=status.running,
        asterisk_message=status.message,
        version=_first_line(version.output),
        uptime=_first_line(uptime.output),
        endpoints_ok=endpoints.ok,
        contacts_count=len(contacts),
        active_calls_count=len(channels),
        trunk_registered=any(item.get("status") == "enregistre" for item in registrations.values()),
        recent_errors=errors.output,
    )


def _first_line(value: str) -> str:
    return next((line for line in value.splitlines() if line.strip()), "-")
