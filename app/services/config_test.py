from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.config import Settings
from app.services.asterisk import GENERATED_FILES, render_configs
from app.services.config_validation import ConfigIssue, validate_config


@dataclass(frozen=True)
class ConfigTestResult:
    ok: bool
    checks: list[ConfigIssue]


def run_generated_config_test(db: Session, settings: Settings) -> ConfigTestResult:
    checks = list(validate_config(db, settings))
    try:
        configs = render_configs(db, settings)
    except Exception as exc:  # noqa: BLE001 - the UI needs the render failure reason.
        checks.append(ConfigIssue("error", f"Generation impossible : {exc}"))
        return ConfigTestResult(ok=False, checks=checks)

    for filename in GENERATED_FILES:
        content = configs.get(filename, "")
        if not content.strip():
            checks.append(ConfigIssue("error", f"{filename} est vide."))
        if "{{" in content or "{%" in content:
            checks.append(ConfigIssue("error", f"{filename} contient encore des marqueurs de template."))

    _check_required_content(checks, configs)
    return ConfigTestResult(ok=not any(check.blocking for check in checks), checks=checks)


def _check_required_content(checks: list[ConfigIssue], configs: dict[str, str]) -> None:
    required = {
        "pjsip_minipbx.conf": ["[transport-udp]", "type=transport"],
        "extensions_minipbx.conf": ["[minipbx-internal]", "[minipbx-inbound]"],
        "voicemail_minipbx.conf": ["[default]"],
        "manager_minipbx.conf": ["[general]"],
        "rtp.conf": ["rtpstart=", "rtpend="],
    }
    for filename, markers in required.items():
        content = configs.get(filename, "")
        for marker in markers:
            if marker not in content:
                checks.append(ConfigIssue("error", f"{filename} ne contient pas le marqueur attendu {marker}."))
