from datetime import date
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.models import Extension
from app.services.auth import current_admin, has_admin
from app.services.cdr import read_call_records, records_to_csv
from app.templating import templates

router = APIRouter(prefix="/calls")


def _guard(request: Request, db: Session) -> RedirectResponse | None:
    if not has_admin(db):
        return RedirectResponse("/setup", status_code=303)
    if not current_admin(request, db):
        return RedirectResponse("/login", status_code=303)
    return None


@router.get("", response_class=HTMLResponse)
def list_calls(
    request: Request,
    call_date: str = Query("", alias="date"),
    extension: str = "",
    direction: str = "all",
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    guarded = _guard(request, db)
    if guarded:
        return guarded

    extensions = list(db.scalars(select(Extension).order_by(Extension.number)))
    extension_numbers = {item.number for item in extensions}
    selected_day, error = _parse_filter_date(call_date)
    records = []
    if not error:
        records = read_call_records(
            settings.cdr_csv_path,
            extension_numbers,
            day=selected_day,
            extension=extension or None,
            direction=direction,
        )
    export_query = urlencode(
        {
            key: value
            for key, value in {
                "date": call_date,
                "extension": extension,
                "direction": direction,
            }.items()
            if value
        }
    )
    return templates.TemplateResponse(
        "calls/list.html",
        {
            "request": request,
            "records": records,
            "extensions": extensions,
            "filters": {"date": call_date, "extension": extension, "direction": direction},
            "export_query": export_query,
            "cdr_path": settings.cdr_csv_path,
            "error": error,
        },
    )


@router.get("/export.csv")
def export_calls(
    request: Request,
    call_date: str = Query("", alias="date"),
    extension: str = "",
    direction: str = "all",
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    guarded = _guard(request, db)
    if guarded:
        return guarded

    extension_numbers = set(db.scalars(select(Extension.number)))
    selected_day, error = _parse_filter_date(call_date)
    records = []
    if not error:
        records = read_call_records(
            settings.cdr_csv_path,
            extension_numbers,
            day=selected_day,
            extension=extension or None,
            direction=direction,
            limit=None,
        )
    return Response(
        records_to_csv(records),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=minipbx-calls.csv"},
    )


def _parse_filter_date(value: str) -> tuple[date | None, str | None]:
    if not value:
        return None, None
    try:
        return date.fromisoformat(value), None
    except ValueError:
        return None, "La date doit etre au format AAAA-MM-JJ."
