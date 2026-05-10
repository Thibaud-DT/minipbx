import io
import wave

from tests.test_auth_flow import create_logged_client
from app.database import SessionLocal
from app.models import IvrMenu


def test_create_ivr_menu_rejects_tts_when_backend_is_disabled():
    client = create_logged_client()
    client.post(
        "/extensions",
        data={
            "number": "100",
            "display_name": "Accueil",
            "email": "",
            "voicemail_enabled": "on",
            "outbound_enabled": "on",
        },
        follow_redirects=False,
    )

    created = client.post(
        "/ivr",
        data={
            "name": "Standard accueil",
            "number": "700",
            "prompt_mode": "tts",
            "prompt_text": "Bonjour, tapez 1 pour l'accueil",
            "timeout_seconds": "8",
            "fallback_type": "hangup",
            "enabled": "on",
            "option_digits": ["1"],
            "option_destination_types": ["extension"],
            "option_destination_targets": ["100"],
            "next_url": "/settings?tab=ivr",
        },
        follow_redirects=False,
    )
    assert created.status_code == 303
    assert created.headers["location"] == "/settings?tab=ivr&error=tts-indisponible"


def test_create_ivr_menu_with_recorded_prompt(tmp_path):
    client = create_logged_client()
    client.post(
        "/extensions",
        data={
            "number": "100",
            "display_name": "Accueil",
            "email": "",
            "voicemail_enabled": "on",
            "outbound_enabled": "on",
        },
        follow_redirects=False,
    )

    created = client.post(
        "/ivr",
        data={
            "name": "Standard vocal",
            "number": "701",
            "prompt_mode": "recording",
            "timeout_seconds": "8",
            "fallback_type": "hangup",
            "enabled": "on",
            "option_digits": ["1"],
            "option_destination_types": ["extension"],
            "option_destination_targets": ["100"],
            "next_url": "/settings?tab=ivr",
        },
        files={"prompt_file": ("message.wav", _wav_bytes(rate=48000, channels=2), "audio/wav")},
        follow_redirects=False,
    )
    assert created.status_code == 303
    assert created.headers["location"] == "/settings?tab=ivr"

    page = client.get("/settings?tab=ivr")
    assert page.status_code == 200
    assert "Standard vocal" in page.text
    assert "Enregistrement" in page.text
    with SessionLocal() as db:
        menu = db.get(IvrMenu, 1)
        assert menu is not None
        with wave.open(menu.prompt_audio_path, "rb") as wav_file:
            assert wav_file.getframerate() == 8000
            assert wav_file.getnchannels() == 1
            assert wav_file.getsampwidth() == 2


def test_update_ivr_menu_keeps_existing_recorded_prompt():
    client = create_logged_client()
    client.post(
        "/extensions",
        data={
            "number": "100",
            "display_name": "Accueil",
            "email": "",
            "voicemail_enabled": "on",
            "outbound_enabled": "on",
        },
        follow_redirects=False,
    )
    client.post(
        "/extensions",
        data={
            "number": "101",
            "display_name": "Support",
            "email": "",
            "voicemail_enabled": "on",
            "outbound_enabled": "on",
        },
        follow_redirects=False,
    )
    created = client.post(
        "/ivr",
        data={
            "name": "Standard vocal",
            "number": "701",
            "prompt_mode": "recording",
            "timeout_seconds": "8",
            "fallback_type": "hangup",
            "enabled": "on",
            "option_digits": ["1"],
            "option_destination_types": ["extension"],
            "option_destination_targets": ["100"],
            "next_url": "/settings?tab=ivr",
        },
        files={"prompt_file": ("message.wav", _wav_bytes(rate=48000, channels=2), "audio/wav")},
        follow_redirects=False,
    )
    assert created.status_code == 303

    updated = client.post(
        "/ivr/1",
        data={
            "name": "Standard support",
            "number": "702",
            "prompt_mode": "recording",
            "prompt_text": "",
            "timeout_seconds": "12",
            "fallback_type": "extension",
            "fallback_target": "100",
            "enabled": "on",
            "option_digits": ["1"],
            "option_destination_types": ["extension"],
            "option_destination_targets": ["101"],
            "next_url": "/settings?tab=ivr",
        },
        follow_redirects=False,
    )

    assert updated.status_code == 303
    assert updated.headers["location"] == "/settings?tab=ivr"
    page = client.get("/settings?tab=ivr")
    assert "Standard support" in page.text
    assert "702" in page.text
    assert "/ivr/1/edit" in page.text
    edit_page = client.get("/ivr/1/edit")
    assert edit_page.status_code == 200
    assert "Standard 702" in edit_page.text
    assert "Standard support" in edit_page.text
    with SessionLocal() as db:
        menu = db.get(IvrMenu, 1)
        assert menu is not None
        assert menu.number == "702"
        assert menu.prompt_audio_path
        assert menu.options[0].destination_target == "101"


def _wav_bytes(rate: int = 8000, channels: int = 1) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(2)
        wav_file.setframerate(rate)
        wav_file.writeframes(b"\x00\x00" * channels * (rate // 10))
    return buffer.getvalue()
