from fastapi.testclient import TestClient
from unittest.mock import patch

from app.database import SessionLocal
from app.main import app
from app.models import AdminUser, Extension, PbxSettings, SipTrunk


def test_setup_login_and_dashboard_flow():
    client = TestClient(app)

    setup = client.get("/setup")
    assert setup.status_code == 200

    created = client.post(
        "/setup",
        data={"username": "admin", "password": "long-password", "password_confirm": "long-password"},
        follow_redirects=False,
    )
    assert created.status_code == 303
    assert created.headers["location"] == "/dashboard"

    dashboard = client.get("/dashboard")
    assert dashboard.status_code == 200
    assert "Dashboard" in dashboard.text


def test_setup_can_create_initial_pbx_settings_extension_and_trunk():
    client = TestClient(app)

    created = client.post(
        "/setup",
        data={
            "username": "admin",
            "password": "long-password",
            "password_confirm": "long-password",
            "network_mode": "bridge",
            "sip_port": "5060",
            "rtp_start": "12000",
            "rtp_end": "12100",
            "external_address": "192.168.1.42",
            "local_net": "172.18.0.0/16",
            "first_extension_number": "100",
            "first_extension_name": "Accueil",
            "first_extension_secret": "extension-secret",
            "trunk_name": "Operateur",
            "trunk_host": "sip.example.test",
            "trunk_username": "account",
            "trunk_password": "trunk-secret",
            "trunk_from_user": "0123456789",
            "trunk_from_domain": "sip.example.test",
        },
        follow_redirects=False,
    )

    assert created.status_code == 303
    assert created.headers["location"] == "/extensions/1/edit"
    with SessionLocal() as db:
        pbx_settings = db.get(PbxSettings, 1)
        extension = db.query(Extension).filter_by(number="100").one()
        trunk = db.query(SipTrunk).filter_by(name="Operateur").one()
        assert pbx_settings is not None
        assert pbx_settings.network_mode == "bridge"
        assert pbx_settings.rtp_start == 12000
        assert pbx_settings.external_address == "192.168.1.42"
        assert extension.display_name == "Accueil"
        assert extension.sip_secret == "extension-secret"
        assert trunk.host == "sip.example.test"
        assert trunk.password_secret == "trunk-secret"


def test_setup_generated_sip_secret_is_alphanumeric():
    client = TestClient(app)

    response = client.post(
        "/setup",
        data={
            "username": "admin",
            "password": "long-password",
            "password_confirm": "long-password",
            "first_extension_number": "100",
            "first_extension_name": "Accueil",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    with SessionLocal() as db:
        extension = db.query(Extension).filter_by(number="100").one()
        assert len(extension.sip_secret) == 24
        assert extension.sip_secret.isalnum()


def test_setup_keeps_created_data_when_initial_apply_fails():
    client = TestClient(app)

    with patch("app.routes.auth.apply_revision", side_effect=RuntimeError("reload failed")):
        response = client.post(
            "/setup",
            data={
                "username": "admin",
                "password": "long-password",
                "password_confirm": "long-password",
                "first_extension_number": "100",
                "first_extension_name": "Accueil",
            },
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard"
    with SessionLocal() as db:
        assert db.query(AdminUser).count() == 1
        assert db.query(Extension).filter_by(number="100").count() == 1

    dashboard = client.get("/dashboard")
    assert dashboard.status_code == 200
    assert "configuration Asterisk initiale" in dashboard.text


def test_setup_rolls_back_admin_when_initial_save_fails():
    client = TestClient(app, raise_server_exceptions=False)

    with patch("app.routes.auth.save_pbx_settings", side_effect=RuntimeError("boom")):
        response = client.post(
            "/setup",
            data={"username": "admin", "password": "long-password", "password_confirm": "long-password"},
            follow_redirects=False,
        )

    assert response.status_code == 500
    with SessionLocal() as db:
        assert db.query(AdminUser).count() == 0


def create_logged_client() -> TestClient:
    client = TestClient(app)
    response = client.post(
        "/setup",
        data={"username": "admin", "password": "long-password", "password_confirm": "long-password"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return client
