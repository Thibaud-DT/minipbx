from pathlib import Path

from app.services.cdr import read_call_records, records_to_csv


def test_read_call_records_filters_and_infers_direction(tmp_path: Path):
    cdr_path = tmp_path / "Master.csv"
    cdr_path.write_text(
        "\n".join(
            [
                '"","100","101","minipbx-internal","","PJSIP/100","","Dial","","2026-05-09 10:00:00","2026-05-09 10:00:02","2026-05-09 10:00:12","12","10","ANSWERED","","1",""',
                '"","100","0123456789","minipbx-outbound","","PJSIP/100","","Dial","","2026-05-09 10:02:00","","2026-05-09 10:02:05","5","0","NO ANSWER","","2",""',
                '"","0123456789","101","minipbx-inbound","","PJSIP/trunk","","Dial","","2026-05-08 09:00:00","2026-05-08 09:00:02","2026-05-08 09:01:00","60","58","ANSWERED","","3",""',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    records = read_call_records(cdr_path, {"100", "101"}, extension="100")

    assert [record.direction for record in records] == ["sortant", "interne"]
    assert records[0].src == "100"
    assert records[0].dst == "0123456789"


def test_records_to_csv_escapes_values():
    cdr_path = Path(__file__).parent / "missing.csv"

    csv_output = records_to_csv(read_call_records(cdr_path, {"100"}))

    assert csv_output == "date,appelant,appele,direction,statut,duree,billsec\n"
