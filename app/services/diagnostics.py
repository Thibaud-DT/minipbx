import re
import subprocess
from dataclasses import dataclass

from app.config import Settings


SAFE_COMMANDS = {
    "endpoints": "pjsip show endpoints",
    "contacts": "pjsip show contacts",
    "registrations": "pjsip show registrations",
    "transports": "pjsip show transports",
    "channels": "core show channels concise",
}

RTP_DEBUG_COMMANDS = {
    "on": "rtp set debug on",
    "off": "rtp set debug off",
}


@dataclass(frozen=True)
class DiagnosticResult:
    name: str
    command: str
    ok: bool
    output: str


def collect_diagnostics(settings: Settings) -> list[DiagnosticResult]:
    if not settings.asterisk_apply_enabled:
        return [
            DiagnosticResult(
                name="Asterisk",
                command="",
                ok=False,
                output="Diagnostics Asterisk desactives dans ce mode.",
            )
        ]
    return [
        _run_asterisk_rx(label, command)
        for label, command in [
            ("Endpoints PJSIP", SAFE_COMMANDS["endpoints"]),
            ("Contacts PJSIP", SAFE_COMMANDS["contacts"]),
            ("Enregistrements trunk", SAFE_COMMANDS["registrations"]),
            ("Transports PJSIP", SAFE_COMMANDS["transports"]),
            ("Canaux actifs", SAFE_COMMANDS["channels"]),
        ]
    ]


def check_dialplan_extension(settings: Settings, number: str) -> DiagnosticResult:
    if not settings.asterisk_apply_enabled:
        return DiagnosticResult(
            name=f"Dialplan {number}",
            command="",
            ok=False,
            output="Diagnostic dialplan indisponible dans ce mode.",
        )
    if not number.isdigit():
        return DiagnosticResult(
            name=f"Dialplan {number}",
            command="",
            ok=False,
            output="Numero invalide.",
        )
    command = f"dialplan show {number}@minipbx-internal"
    return _run_asterisk_rx(f"Dialplan standard {number}", command)


def set_rtp_debug(settings: Settings, enabled: bool) -> DiagnosticResult:
    if not settings.asterisk_apply_enabled:
        return DiagnosticResult(
            name="Debug RTP",
            command="",
            ok=False,
            output="Debug RTP indisponible dans ce mode.",
        )
    command = RTP_DEBUG_COMMANDS["on" if enabled else "off"]
    return _run_asterisk_rx("Debug RTP", command)


def _run_asterisk_rx(name: str, command: str) -> DiagnosticResult:
    try:
        result = subprocess.run(
            ["asterisk", "-rx", command],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return DiagnosticResult(name=name, command=command, ok=False, output=str(exc))

    output = "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part)
    return DiagnosticResult(
        name=name,
        command=command,
        ok=result.returncode == 0,
        output=_redact(output) or "Aucune sortie.",
    )


def _redact(value: str) -> str:
    patterns = [
        (re.compile(r"(password\s*=\s*)\S+", re.IGNORECASE), r"\1***"),
        (re.compile(r"(secret\s*=\s*)\S+", re.IGNORECASE), r"\1***"),
        (re.compile(r"(Authorization:\s*).+", re.IGNORECASE), r"\1***"),
        (re.compile(r"(Proxy-Authorization:\s*).+", re.IGNORECASE), r"\1***"),
    ]
    redacted = value
    for pattern, replacement in patterns:
        redacted = pattern.sub(replacement, redacted)
    return redacted
