import re
import subprocess
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Extension, SipTrunk
from app.services.ami import AMIState, ami_event_hub


@dataclass(frozen=True)
class ExtensionPresence:
    number: str
    display_name: str
    enabled: bool
    registered: bool
    contact_uri: str
    status: str
    latency_ms: str
    active_channels: int


@dataclass(frozen=True)
class ActiveCall:
    channel: str
    state: str
    caller_id: str
    context: str
    extension: str
    application: str
    data: str
    duration: str
    bridged_channel: str


@dataclass(frozen=True)
class TrunkPresence:
    name: str
    host: str
    username: str
    enabled: bool
    registered: bool
    status: str
    registration: str


@dataclass(frozen=True)
class MonitoringSnapshot:
    enabled: bool
    message: str
    extensions: list[ExtensionPresence]
    trunks: list[TrunkPresence]
    active_calls: list[ActiveCall]

    @property
    def registered_count(self) -> int:
        return len([extension for extension in self.extensions if extension.registered])

    @property
    def active_call_count(self) -> int:
        return len(self.active_calls)

    def as_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "message": self.message,
            "registered_count": self.registered_count,
            "active_call_count": self.active_call_count,
            "extensions": [
                {
                    "number": extension.number,
                    "display_name": extension.display_name,
                    "enabled": extension.enabled,
                    "registered": extension.registered,
                    "contact_uri": extension.contact_uri,
                    "status": extension.status,
                    "latency_ms": extension.latency_ms,
                    "active_channels": extension.active_channels,
                }
                for extension in self.extensions
            ],
            "trunks": [
                {
                    "name": trunk.name,
                    "host": trunk.host,
                    "username": trunk.username,
                    "enabled": trunk.enabled,
                    "registered": trunk.registered,
                    "status": trunk.status,
                    "registration": trunk.registration,
                }
                for trunk in self.trunks
            ],
            "active_calls": [
                {
                    "channel": call.channel,
                    "state": call.state,
                    "caller_id": call.caller_id,
                    "context": call.context,
                    "extension": call.extension,
                    "application": call.application,
                    "data": call.data,
                    "duration": call.duration,
                    "bridged_channel": call.bridged_channel,
                }
                for call in self.active_calls
            ],
        }


def collect_monitoring_snapshot(db: Session, settings: Settings) -> MonitoringSnapshot:
    extensions = list(db.scalars(select(Extension).order_by(Extension.number)))
    trunks = list(db.scalars(select(SipTrunk).order_by(SipTrunk.id)))
    if not settings.asterisk_apply_enabled:
        return MonitoringSnapshot(
            enabled=False,
            message="Supervision Asterisk desactivee dans ce mode.",
            extensions=[
                ExtensionPresence(
                    number=extension.number,
                    display_name=extension.display_name,
                    enabled=extension.enabled,
                    registered=False,
                    contact_uri="",
                    status="non surveille",
                    latency_ms="-",
                    active_channels=0,
                )
                for extension in extensions
            ],
            trunks=[
                TrunkPresence(
                    name=trunk.name,
                    host=trunk.host,
                    username=trunk.username,
                    enabled=trunk.enabled,
                    registered=False,
                    status="non surveille",
                    registration="",
                )
                for trunk in trunks
            ],
            active_calls=[],
        )

    ami_state = ami_event_hub.snapshot()
    contacts_output = _asterisk_rx("pjsip show contacts")
    registrations_output = _asterisk_rx("pjsip show registrations")
    cli_contacts = parse_contacts(contacts_output)
    contacts = {**ami_state.contacts, **cli_contacts}
    registrations = parse_registrations(registrations_output)
    if ami_state.connected:
        active_calls = _active_calls_from_ami(ami_state)
        message = "Supervision active via PJSIP et evenements AMI."
    else:
        channels_output = _asterisk_rx("core show channels concise")
        active_calls = parse_channels(channels_output)
        message = "Supervision active via commandes Asterisk."
    channel_counts = _channel_counts_by_extension(active_calls)

    return MonitoringSnapshot(
        enabled=True,
        message=message,
        extensions=[
            ExtensionPresence(
                number=extension.number,
                display_name=extension.display_name,
                enabled=extension.enabled,
                registered=_contact_for_extension(extension, contacts) is not None,
                contact_uri=(_contact_for_extension(extension, contacts) or {}).get("uri", ""),
                status=(_contact_for_extension(extension, contacts) or {}).get("status", "non enregistre"),
                latency_ms=(_contact_for_extension(extension, contacts) or {}).get("latency", "-"),
                active_channels=channel_counts.get(extension.sip_username, 0) + (
                    channel_counts.get(extension.number, 0) if extension.number != extension.sip_username else 0
                ),
            )
            for extension in extensions
        ],
        trunks=[
            TrunkPresence(
                name=trunk.name,
                host=trunk.host,
                username=trunk.username,
                enabled=trunk.enabled,
                registered=registrations.get("trunk-main-registration", {}).get("registered", False),
                status=(
                    registrations.get("trunk-main-registration", {}).get("status", "non surveille")
                    if trunk.enabled
                    else "desactive"
                ),
                registration=registrations.get("trunk-main-registration", {}).get("registration", ""),
            )
            for trunk in trunks
        ],
        active_calls=active_calls,
    )


def _active_calls_from_ami(ami_state: AMIState) -> list[ActiveCall]:
    calls = []
    for channel in ami_state.channels.values():
        calls.append(
            ActiveCall(
                channel=channel.get("channel", ""),
                state=channel.get("state", ""),
                caller_id=channel.get("caller_id", ""),
                context=channel.get("context", ""),
                extension=channel.get("extension", ""),
                application=channel.get("application", ""),
                data=channel.get("data", ""),
                duration=channel.get("duration", ""),
                bridged_channel=channel.get("bridged_channel", ""),
            )
        )
    return calls


def parse_contacts(output: str) -> dict[str, dict[str, str]]:
    contacts: dict[str, dict[str, str]] = {}
    for line in output.splitlines():
        if "Contact:" not in line:
            continue
        match = re.search(r"Contact:\s+([^/\s]+)/(\S+)\s+.*?\s+(Avail|Unavail|NonQual|Unknown|Reachable|Unreachable)\s+([\d.]+|nan)?", line)
        if not match:
            continue
        endpoint, uri, status, latency = match.groups()
        contacts[endpoint] = {
            "uri": uri,
            "status": _normalize_contact_status(status),
            "latency": latency or "-",
        }
    return contacts


def parse_channels(output: str) -> list[ActiveCall]:
    calls = []
    for line in output.splitlines():
        if not line.strip() or "!" not in line:
            continue
        parts = line.split("!")
        if len(parts) < 12:
            continue
        calls.append(
            ActiveCall(
                channel=parts[0],
                context=parts[1],
                extension=parts[2],
                state=parts[4],
                application=parts[5],
                data=parts[6],
                caller_id=parts[7],
                duration=parts[11] if len(parts) > 11 else "",
                bridged_channel=parts[12] if len(parts) > 12 else "",
            )
        )
    return calls


def parse_registrations(output: str) -> dict[str, dict[str, str | bool]]:
    registrations: dict[str, dict[str, str | bool]] = {}
    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith("=") or line.startswith("<"):
            continue
        if "/" not in line or "sip:" not in line:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        registration = parts[0].split("/", 1)[0]
        status_text = " ".join(parts[2:] if len(parts) > 2 else parts[1:])
        normalized = _normalize_registration_status(status_text)
        registrations[registration] = {
            "registration": registration,
            "status": normalized,
            "registered": normalized == "enregistre",
        }
    return registrations


def _asterisk_rx(command: str) -> str:
    try:
        result = subprocess.run(
            ["asterisk", "-rx", command],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return str(exc)
    return "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part)


def _channel_counts_by_extension(calls: list[ActiveCall]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for call in calls:
        for endpoint in re.findall(r"PJSIP/([^-!\s]+)-", f"{call.channel} {call.bridged_channel}"):
            counts[endpoint] = counts.get(endpoint, 0) + 1
    return counts


def _contact_for_extension(extension: Extension, contacts: dict[str, dict[str, str]]) -> dict[str, str] | None:
    return contacts.get(extension.sip_username) or contacts.get(extension.number)


def _normalize_contact_status(value: str) -> str:
    return {
        "Avail": "enregistre",
        "Reachable": "enregistre",
        "Unavail": "injoignable",
        "Unreachable": "injoignable",
        "NonQual": "non qualifie",
        "Unknown": "inconnu",
    }.get(value, value)


def _normalize_registration_status(value: str) -> str:
    lower = value.lower()
    if "unregistered" in lower or "stopped" in lower:
        return "non enregistre"
    if "registered" in lower:
        return "enregistre"
    if "rejected" in lower or "forbidden" in lower or "fatal" in lower:
        return "rejete"
    if "timeout" in lower or "unreachable" in lower:
        return "injoignable"
    return value.strip() or "inconnu"
