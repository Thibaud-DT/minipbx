from tests.test_auth_flow import create_logged_client


def test_menu_shows_configuration_state_and_applies_current_config():
    client = create_logged_client()

    dashboard = client.get("/dashboard")
    assert dashboard.status_code == 200
    assert "Modification a appliquer" in dashboard.text
    assert 'action="/config/apply-current"' in dashboard.text

    applied = client.post(
        "/config/apply-current",
        data={"next_url": "/dashboard"},
        follow_redirects=False,
    )
    assert applied.status_code == 303
    assert applied.headers["location"] == "/dashboard"

    dashboard = client.get("/dashboard")
    assert dashboard.status_code == 200
    assert "Configuration a jour" in dashboard.text
    assert 'action="/config/apply-current"' not in dashboard.text

    created = client.post(
        "/extensions",
        data={
            "number": "101",
            "display_name": "Accueil",
            "email": "",
            "voicemail_enabled": "on",
            "outbound_enabled": "on",
            "next_url": "/settings?tab=extensions",
        },
        follow_redirects=False,
    )
    assert created.status_code == 303

    dashboard = client.get("/dashboard")
    assert dashboard.status_code == 200
    assert "Modification a appliquer" in dashboard.text
