from unittest.mock import Mock, patch

from app.config import Settings
from app.services.config_test import run_generated_config_test
from app.services.health import collect_health
from tests.test_auth_flow import create_logged_client


def test_health_page_shows_config_test_in_disabled_mode():
    client = create_logged_client()

    page = client.get("/health")

    assert page.status_code == 200
    assert "Sante Asterisk" in page.text
    assert "Test de configuration avant application" in page.text
    assert "Avertissement" in page.text


def test_readiness_endpoint_is_public():
    client = create_logged_client()

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["database"] is True


def test_collect_health_parses_asterisk_outputs():
    settings = Settings(secret_key="test", asterisk_apply_enabled=True)

    def fake_run(name: str, command: str):
        result = Mock()
        result.ok = True
        if command == "core show version":
            result.output = "Asterisk 20.6.0 built by test"
        elif command == "core show uptime":
            result.output = "System uptime: 1 hour"
        elif command == "pjsip show contacts":
            result.output = "  Contact:  100/sip:100@192.168.1.10:5060  abc Avail 12.3"
        elif command == "core show channels concise":
            result.output = "PJSIP/100-00000001!minipbx-internal!101!1!Up!Dial!PJSIP/101!100!101!0!0!12!PJSIP/101-00000002"
        elif command == "pjsip show registrations":
            result.output = "trunk-main/sip:sip.example.test  trunk-main  Registered"
        else:
            result.output = "OK"
        return result

    with patch("app.services.health.get_asterisk_status") as status, patch("app.services.health._run_asterisk_rx", side_effect=fake_run):
        status.return_value.running = True
        status.return_value.message = "Asterisk repond"
        health = collect_health(settings)

    assert health.asterisk_running is True
    assert health.version == "Asterisk 20.6.0 built by test"
    assert health.contacts_count == 1
    assert health.active_calls_count == 1
    assert health.trunk_registered is True


def test_generated_config_test_reports_invalid_rtp_range():
    client = create_logged_client()
    from app.database import SessionLocal
    from app.models import PbxSettings

    with SessionLocal() as db:
        stored = db.get(PbxSettings, 1)
        assert stored is not None
        stored.rtp_start = 20000
        stored.rtp_end = 10000
        db.add(stored)
        db.commit()
        result = run_generated_config_test(db, Settings(secret_key="test", asterisk_apply_enabled=False))

    assert result.ok is False
    assert any("plage RTP est invalide" in issue.message for issue in result.checks)
