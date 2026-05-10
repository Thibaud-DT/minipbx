import os
from pathlib import Path

from tests.test_auth_flow import create_logged_client


def test_voicemail_page_lists_downloads_and_deletes_message():
    client = create_logged_client()
    client.post(
        "/extensions",
        data={
            "number": "100",
            "display_name": "Accueil",
            "voicemail_enabled": "on",
            "outbound_enabled": "on",
        },
        follow_redirects=False,
    )
    inbox = Path(os.environ["MINIPBX_VOICEMAIL_SPOOL_DIR"]) / "100" / "INBOX"
    inbox.mkdir(parents=True, exist_ok=True)
    audio = inbox / "msg0000.wav"
    metadata = inbox / "msg0000.txt"
    audio.write_bytes(b"RIFF0000WAVEfmt ")
    metadata.write_text(
        """[message]
callerid="Client" <0123456789>
origdate=Sun May 10 13:30:00 2026
duration=7
""",
        encoding="utf-8",
    )

    page = client.get("/voicemail")

    assert page.status_code == 200
    assert "100 - Accueil" in page.text
    assert "Client" in page.text
    assert "/voicemail/100/INBOX/msg0000.wav" in page.text

    downloaded = client.get("/voicemail/100/INBOX/msg0000.wav")
    assert downloaded.status_code == 200
    assert downloaded.content == b"RIFF0000WAVEfmt "

    deleted = client.post("/voicemail/100/INBOX/msg0000.wav/delete", follow_redirects=False)

    assert deleted.status_code == 303
    assert deleted.headers["location"] == "/voicemail"
    assert not audio.exists()
    assert not metadata.exists()
