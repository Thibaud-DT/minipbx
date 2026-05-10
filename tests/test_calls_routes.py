import os
from pathlib import Path

from tests.test_auth_flow import create_logged_client


def test_calls_page_and_csv_export():
    client = create_logged_client()
    client.post(
        "/extensions",
        data={
            "number": "100",
            "display_name": "Bureau",
            "voicemail_enabled": "on",
            "outbound_enabled": "on",
        },
    )
    client.post(
        "/extensions",
        data={
            "number": "101",
            "display_name": "Accueil",
            "voicemail_enabled": "on",
            "outbound_enabled": "on",
        },
    )
    cdr_path = Path(os.environ["MINIPBX_CDR_CSV_PATH"])
    cdr_path.parent.mkdir(parents=True, exist_ok=True)
    cdr_path.write_text(
        '"","100","101","minipbx-internal","","PJSIP/100","","Dial","","2026-05-09 10:00:00","2026-05-09 10:00:01","2026-05-09 10:00:08","8","7","ANSWERED","","1",""\n'
        '"","0123456789","100","minipbx-internal","","PJSIP/trunk","","Dial","","2026-05-09 11:00:00","2026-05-09 11:00:01","2026-05-09 11:00:08","8","7","ANSWERED","","2",""\n',
        encoding="utf-8",
    )

    page = client.get("/calls")
    assert page.status_code == 200
    assert "Journal d'appels" in page.text
    assert "interne" in page.text

    export = client.get("/calls/export.csv?direction=interne")
    assert export.status_code == 200
    assert export.headers["content-disposition"] == "attachment; filename=minipbx-calls.csv"
    assert "2026-05-09 10:00:00,100,101,interne,ANSWERED,8,7" in export.text
