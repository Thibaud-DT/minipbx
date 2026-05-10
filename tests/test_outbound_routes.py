from tests.test_auth_flow import create_logged_client


def test_save_outbound_rule():
    client = create_logged_client()

    saved = client.post(
        "/outbound",
        data={
            "name": "Sortant",
            "prefix": "9",
            "emergency_numbers": "15,17,18,112",
            "allow_national": "on",
            "allow_mobile": "on",
        },
        follow_redirects=False,
    )

    assert saved.status_code == 303
    page = client.get("/outbound")
    assert page.status_code == 200
    assert "Sortant" in page.text
    assert "International : bloque" in page.text
