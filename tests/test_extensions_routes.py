import io
import wave

from tests.test_auth_flow import create_logged_client
from app.database import SessionLocal
from app.models import Extension


def test_create_edit_regenerate_and_delete_extension():
    client = create_logged_client()

    created = client.post(
        "/extensions",
        data={
            "number": "101",
            "display_name": "Accueil",
            "email": "accueil@example.test",
            "voicemail_enabled": "on",
            "outbound_enabled": "on",
        },
        follow_redirects=False,
    )
    assert created.status_code == 303

    edit_page = client.get("/extensions/1/edit")
    assert edit_page.status_code == 200
    assert "Accueil" in edit_page.text
    assert "Mot de passe SIP" in edit_page.text
    assert "Afficher le mot de passe" in edit_page.text

    updated = client.post(
        "/extensions/1",
        data={
            "number": "102",
            "display_name": "Direction",
            "email": "",
            "voicemail_pin": "1234",
            "voicemail_enabled": "on",
            "outbound_enabled": "on",
            "inbound_enabled": "on",
            "enabled": "on",
        },
        follow_redirects=False,
    )
    assert updated.status_code == 303

    regenerated = client.post("/extensions/1/regenerate-secret", follow_redirects=False)
    assert regenerated.status_code == 303
    with SessionLocal() as db:
        extension = db.get(Extension, 1)
        assert extension is not None
        assert extension.sip_secret.isalnum()

    deleted = client.post("/extensions/1/delete", follow_redirects=False)
    assert deleted.status_code == 303

    list_page = client.get("/extensions")
    assert "Aucune extension" in list_page.text


def test_update_extension_with_voicemail_recorded_greeting():
    client = create_logged_client()
    client.post(
        "/extensions",
        data={
            "number": "101",
            "display_name": "Accueil",
            "voicemail_enabled": "on",
            "outbound_enabled": "on",
        },
        follow_redirects=False,
    )

    updated = client.post(
        "/extensions/1",
        data={
            "number": "101",
            "display_name": "Accueil",
            "email": "",
            "voicemail_pin": "1234",
            "voicemail_enabled": "on",
            "outbound_enabled": "on",
            "inbound_enabled": "on",
            "enabled": "on",
            "voicemail_greeting_mode": "recording",
            "voicemail_greeting_text": "",
        },
        files={"voicemail_greeting_file": ("message.wav", _wav_bytes(rate=48000, channels=2), "audio/wav")},
        follow_redirects=False,
    )

    assert updated.status_code == 303
    with SessionLocal() as db:
        extension = db.get(Extension, 1)
        assert extension is not None
        assert extension.voicemail_greeting_mode == "recording"
        assert extension.voicemail_greeting_audio_path
        with wave.open(extension.voicemail_greeting_audio_path, "rb") as wav_file:
            assert wav_file.getframerate() == 8000
            assert wav_file.getnchannels() == 1


def _wav_bytes(rate: int = 8000, channels: int = 1) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(2)
        wav_file.setframerate(rate)
        wav_file.writeframes(b"\x00\x00" * channels * (rate // 10))
    return buffer.getvalue()
