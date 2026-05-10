import csv
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path


CDR_COLUMNS = [
    "accountcode",
    "src",
    "dst",
    "dcontext",
    "clid",
    "channel",
    "dstchannel",
    "lastapp",
    "lastdata",
    "start",
    "answer",
    "end",
    "duration",
    "billsec",
    "disposition",
    "amaflags",
    "uniqueid",
    "userfield",
]


@dataclass(frozen=True)
class CallRecord:
    started_at: datetime | None
    src: str
    dst: str
    disposition: str
    duration: int
    billsec: int
    direction: str
    channel: str
    dstchannel: str


def read_call_records(
    csv_path: Path,
    extension_numbers: set[str],
    day: date | None = None,
    extension: str | None = None,
    direction: str | None = None,
    limit: int | None = 200,
) -> list[CallRecord]:
    if not csv_path.exists():
        return []

    records: list[CallRecord] = []
    with csv_path.open(newline="", encoding="utf-8", errors="replace") as handle:
        reader = csv.reader(handle)
        for row in reader:
            if not row:
                continue
            data = _row_to_dict(row)
            record = _record_from_row(data, extension_numbers)
            if day and record.started_at and record.started_at.date() != day:
                continue
            if extension and extension not in {record.src, record.dst}:
                continue
            if direction and direction != "all" and record.direction != direction:
                continue
            records.append(record)

    records.sort(key=lambda item: item.started_at or datetime.min, reverse=True)
    if limit is not None:
        return records[:limit]
    return records


def records_to_csv(records: list[CallRecord]) -> str:
    rows = [["date", "appelant", "appele", "direction", "statut", "duree", "billsec"]]
    for record in records:
        rows.append(
            [
                record.started_at.isoformat(sep=" ") if record.started_at else "",
                record.src,
                record.dst,
                record.direction,
                record.disposition,
                str(record.duration),
                str(record.billsec),
            ]
        )
    output: list[str] = []
    for row in rows:
        output.append(",".join(_escape_csv_cell(cell) for cell in row))
    return "\n".join(output) + "\n"


def _row_to_dict(row: list[str]) -> dict[str, str]:
    padded = row + [""] * max(0, len(CDR_COLUMNS) - len(row))
    return dict(zip(CDR_COLUMNS, padded, strict=False))


def _record_from_row(row: dict[str, str], extension_numbers: set[str]) -> CallRecord:
    src = row.get("src", "")
    dst = row.get("dst", "")
    return CallRecord(
        started_at=_parse_datetime(row.get("start", "")),
        src=src,
        dst=dst,
        disposition=row.get("disposition", ""),
        duration=_parse_int(row.get("duration", "")),
        billsec=_parse_int(row.get("billsec", "")),
        direction=_infer_direction(src, dst, row.get("dcontext", ""), extension_numbers),
        channel=row.get("channel", ""),
        dstchannel=row.get("dstchannel", ""),
    )


def _infer_direction(src: str, dst: str, context: str, extension_numbers: set[str]) -> str:
    if src in extension_numbers and dst in extension_numbers:
        return "interne"
    if context == "minipbx-inbound" or (src not in extension_numbers and dst in extension_numbers):
        return "entrant"
    if src in extension_numbers and dst not in extension_numbers:
        return "sortant"
    return "inconnu"


def _parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _parse_int(value: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _escape_csv_cell(value: str) -> str:
    if any(char in value for char in [",", '"', "\n"]):
        return '"' + value.replace('"', '""') + '"'
    return value
