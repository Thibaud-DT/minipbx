from sqlalchemy import select

from app.database import SessionLocal
from app.models import ConfigRevision, InboundRoute
from tests.test_auth_flow import create_logged_client


def test_invalid_inbound_route_blocks_generation():
    client = create_logged_client()
    with SessionLocal() as db:
        db.add(
            InboundRoute(
                name="Route invalide",
                open_destination_type="extension",
                open_destination_target="999",
                closed_destination_type="hangup",
            )
        )
        db.commit()

    preview = client.get("/config/preview")
    assert preview.status_code == 200
    assert "Erreur bloquante" in preview.text
    assert "extension active introuvable (999)" in preview.text

    generated = client.post("/config/generate", follow_redirects=False)
    assert generated.status_code == 303
    assert generated.headers["location"] == "/config/preview?validation=failed"

    with SessionLocal() as db:
        revision = db.scalar(select(ConfigRevision).order_by(ConfigRevision.id.desc()).limit(1))
        assert revision is None


def test_config_preview_shows_revision_history_and_applies_selected_revision():
    client = create_logged_client()
    client.post(
        "/extensions",
        data={
            "number": "101",
            "display_name": "Accueil",
            "email": "",
            "voicemail_enabled": "on",
            "outbound_enabled": "on",
        },
    )

    generated = client.post("/config/generate", follow_redirects=False)
    assert generated.status_code == 303

    preview = client.get("/config/preview")
    assert preview.status_code == 200
    assert "Historique des revisions" in preview.text
    assert "Test de configuration" in preview.text
    assert "5 fichiers generes" in preview.text
    assert 'action="/config/revisions/1/apply"' in preview.text

    applied = client.post("/config/revisions/1/apply", follow_redirects=False)
    assert applied.status_code == 303
    assert applied.headers["location"] == "/config/preview"

    with SessionLocal() as db:
        revision = db.get(ConfigRevision, 1)
        assert revision is not None
        assert revision.status == "applied"
