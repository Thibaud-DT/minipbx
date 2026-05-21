from tests.test_auth_flow import create_logged_client


def test_save_trunk_masks_password_and_preview_config():
    client = create_logged_client()

    saved = client.post(
        "/trunk",
        data={
            "name": "Operateur",
            "host": "sip.example.test",
            "username": "account-1",
            "password": "super-secret",
            "from_user": "0123456789",
            "from_domain": "sip.example.test",
            "inbound_match": "85.31.193.213\n85.31.193.214",
            "transport": "udp",
            "enabled": "on",
        },
        follow_redirects=False,
    )
    assert saved.status_code == 303

    trunk_page = client.get("/trunk")
    assert trunk_page.status_code == 200
    assert "Operateur" in trunk_page.text
    assert "super-secret" not in trunk_page.text
    assert "Masque" in trunk_page.text

    preview = client.get("/config/preview?selected=pjsip_minipbx.conf")
    assert preview.status_code == 200
    assert "trunk-main" in preview.text
    assert "sip.example.test" in preview.text
    assert "trunk-main-identify" in preview.text
    assert "match=85.31.193.213" in preview.text
    assert "match=85.31.193.214" in preview.text


def test_save_analog_fxo_trunk_generates_dynamic_aor():
    client = create_logged_client()

    saved = client.post(
        "/trunk",
        data={
            "name": "Grandstream HT813",
            "kind": "analog_fxo",
            "host": "192.168.10.130",
            "username": "fxo900",
            "password": "super-secret",
            "from_user": "",
            "from_domain": "",
            "inbound_match": "192.168.10.130",
            "fxo_stage_method": "1",
            "transport": "udp",
            "enabled": "on",
        },
        follow_redirects=False,
    )
    assert saved.status_code == 303

    preview = client.get("/config/preview?selected=pjsip_minipbx.conf")
    assert preview.status_code == 200
    assert "Passerelle analogique FXO" in client.get("/trunk").text
    assert "Stage Method 1" in client.get("/trunk").text
    assert "auth=trunk-main-auth" in preview.text
    assert "max_contacts=1" in preview.text
    assert "trunk-main-registration" not in preview.text
