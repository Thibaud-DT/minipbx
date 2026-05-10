from tests.test_auth_flow import create_logged_client
from app.database import SessionLocal
from app.models import InboundRoute, PbxSettings


def test_settings_tabs_render_configuration_views():
    client = create_logged_client()

    page = client.get("/settings")
    assert page.status_code == 200
    assert "Configuration" in page.text
    assert "Reglages PBX" in page.text
    assert "/settings?tab=pbx" in page.text
    assert "/settings?tab=trunk" in page.text

    extensions_tab = client.get("/settings?tab=extensions")
    assert extensions_tab.status_code == 200
    assert "Nouvelle extension" in extensions_tab.text

    trunk_tab = client.get("/settings?tab=trunk")
    assert trunk_tab.status_code == 200
    assert "Trunk SIP principal" in trunk_tab.text

    asterisk_tab = client.get("/settings?tab=asterisk")
    assert asterisk_tab.status_code == 200
    assert "manager_minipbx.conf" in asterisk_tab.text


def test_pbx_settings_can_be_updated_from_settings_page():
    client = create_logged_client()

    saved = client.post(
        "/settings/pbx",
        data={
            "network_mode": "bridge",
            "sip_port": "5070",
            "rtp_start": "12000",
            "rtp_end": "12100",
            "external_address": "192.168.1.42",
            "local_net": "172.18.0.0/16",
        },
        follow_redirects=False,
    )

    assert saved.status_code == 303
    assert saved.headers["location"] == "/settings?tab=pbx"
    with SessionLocal() as db:
        pbx_settings = db.get(PbxSettings, 1)
        assert pbx_settings is not None
        assert pbx_settings.network_mode == "bridge"
        assert pbx_settings.sip_port == 5070
        assert pbx_settings.rtp_start == 12000
        assert pbx_settings.rtp_end == 12100
        assert pbx_settings.external_address == "192.168.1.42"
        assert pbx_settings.local_net == "172.18.0.0/16"


def test_validation_issues_are_shown_on_related_settings_tab():
    client = create_logged_client()
    client.post(
        "/settings/pbx",
        data={
            "network_mode": "bridge",
            "sip_port": "5060",
            "rtp_start": "12000",
            "rtp_end": "12100",
            "external_address": "",
            "local_net": "172.18.0.0/16",
        },
    )

    page = client.get("/settings?tab=extensions")

    assert page.status_code == 200
    assert "Controle de cette section" in page.text
    assert "Aucune extension active" in page.text


def test_settings_form_redirects_back_to_active_tab():
    client = create_logged_client()

    created = client.post(
        "/extensions",
        data={
            "number": "100",
            "display_name": "Bureau",
            "voicemail_enabled": "on",
            "outbound_enabled": "on",
            "next_url": "/settings?tab=extensions",
        },
        follow_redirects=False,
    )

    assert created.status_code == 303
    assert created.headers["location"] == "/settings?tab=extensions"

    saved = client.post(
        "/outbound",
        data={
            "name": "Sortant",
            "prefix": "0",
            "emergency_numbers": "15,17,18,112",
            "allow_national": "on",
            "next_url": "/settings?tab=outbound",
        },
        follow_redirects=False,
    )

    assert saved.status_code == 303
    assert saved.headers["location"] == "/settings?tab=outbound"


def test_inbound_route_saves_business_hours():
    client = create_logged_client()
    client.post(
        "/extensions",
        data={
            "number": "100",
            "display_name": "Accueil",
            "voicemail_enabled": "on",
            "outbound_enabled": "on",
            "next_url": "/settings?tab=extensions",
        },
        follow_redirects=False,
    )

    saved = client.post(
        "/inbound",
        data={
            "name": "Route principale",
            "use_business_hours": "on",
            "business_days": ["mon", "tue", "wed", "thu", "fri"],
            "business_open_time": "09:00",
            "business_close_time": "18:00",
            "holiday_dates": "2026-12-25\n2026-01-01",
            "open_destination_type": "extension",
            "open_destination_target": "100",
            "closed_destination_type": "hangup",
            "next_url": "/settings?tab=inbound",
        },
        follow_redirects=False,
    )

    assert saved.status_code == 303
    assert saved.headers["location"] == "/settings?tab=inbound"
    with SessionLocal() as db:
        route = db.query(InboundRoute).first()
        assert route is not None
        assert route.use_business_hours is True
        assert route.business_days == "mon,tue,wed,thu,fri"
        assert route.business_open_time == "09:00"
        assert route.business_close_time == "18:00"
        assert route.holiday_dates == "2026-12-25\n2026-01-01"


def test_multiple_inbound_routes_can_be_created_and_edited():
    client = create_logged_client()
    for number, name in [("100", "Accueil"), ("101", "Support")]:
        client.post(
            "/extensions",
            data={
                "number": number,
                "display_name": name,
                "voicemail_enabled": "on",
                "outbound_enabled": "on",
                "next_url": "/settings?tab=extensions",
            },
            follow_redirects=False,
        )

    default_route = client.post(
        "/inbound",
        data={
            "name": "Defaut",
            "open_destination_type": "extension",
            "open_destination_target": "100",
            "closed_destination_type": "hangup",
            "next_url": "/settings?tab=inbound",
        },
        follow_redirects=False,
    )
    did_route = client.post(
        "/inbound",
        data={
            "name": "Support",
            "did_number": "0123456789",
            "open_destination_type": "extension",
            "open_destination_target": "101",
            "closed_destination_type": "hangup",
            "next_url": "/settings?tab=inbound",
        },
        follow_redirects=False,
    )

    assert default_route.status_code == 303
    assert did_route.status_code == 303
    page = client.get("/settings?tab=inbound")
    assert "Par defaut" in page.text
    assert "0123456789" in page.text
    assert "/inbound/2/edit" in page.text

    edit_page = client.get("/inbound/2/edit")
    assert edit_page.status_code == 200
    assert "0123456789" in edit_page.text

    updated = client.post(
        "/inbound/2",
        data={
            "name": "Support VIP",
            "did_number": "0123456789",
            "open_destination_type": "extension",
            "open_destination_target": "100",
            "closed_destination_type": "hangup",
        },
        follow_redirects=False,
    )

    assert updated.status_code == 303
    with SessionLocal() as db:
        routes = db.query(InboundRoute).order_by(InboundRoute.id).all()
        assert len(routes) == 2
        assert routes[1].name == "Support VIP"
        assert routes[1].open_destination_target == "100"
