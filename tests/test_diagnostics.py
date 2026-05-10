from unittest.mock import Mock, patch

from app.services.diagnostics import _run_asterisk_rx
from tests.test_auth_flow import create_logged_client


def test_diagnostics_page_in_disabled_mode():
    client = create_logged_client()

    page = client.get("/diagnostics")

    assert page.status_code == 200
    assert "Diagnostics" in page.text
    assert "Diagnostics Asterisk desactives dans ce mode" in page.text


def test_diagnostic_output_redacts_secrets():
    completed = Mock()
    completed.returncode = 0
    completed.stdout = "password=very-secret\nAuthorization: Digest sensitive\n"
    completed.stderr = ""

    with patch("app.services.diagnostics.subprocess.run", return_value=completed):
        result = _run_asterisk_rx("Test", "pjsip show endpoint 100")

    assert result.ok is True
    assert "very-secret" not in result.output
    assert "sensitive" not in result.output
    assert "password=***" in result.output
