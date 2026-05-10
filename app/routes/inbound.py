import re

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Extension, InboundRoute, IvrMenu, RingGroup
from app.services.auth import current_admin, has_admin
from app.templating import templates

router = APIRouter(prefix="/inbound")
DESTINATION_TYPES = {"extension", "ring_group", "ivr", "voicemail", "hangup"}
BUSINESS_DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DID_RE = re.compile(r"^\d{2,20}$")


def _guard(request: Request, db: Session) -> RedirectResponse | None:
    if not has_admin(db):
        return RedirectResponse("/setup", status_code=303)
    if not current_admin(request, db):
        return RedirectResponse("/login", status_code=303)
    return None


@router.get("", response_class=HTMLResponse)
def inbound_form(request: Request, db: Session = Depends(get_db)):
    guarded = _guard(request, db)
    if guarded:
        return guarded
    return _render_form(request, db)


@router.get("/{route_id}/edit", response_class=HTMLResponse)
def edit_inbound_route_form(
    route_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    guarded = _guard(request, db)
    if guarded:
        return guarded
    route = db.get(InboundRoute, route_id)
    if not route:
        return RedirectResponse("/settings?tab=inbound", status_code=303)
    return _render_edit_form(request, db, route)


@router.post("")
def save_inbound_route(
    request: Request,
    name: str = Form("Route entrante principale"),
    did_number: str = Form(""),
    open_destination_type: str = Form("extension"),
    open_destination_target: str = Form(""),
    closed_destination_type: str = Form("hangup"),
    closed_destination_target: str = Form(""),
    use_business_hours: bool = Form(False),
    business_days: list[str] = Form([]),
    business_open_time: str = Form("09:00"),
    business_close_time: str = Form("18:00"),
    holiday_dates: str = Form(""),
    next_url: str = Form(""),
    db: Session = Depends(get_db),
):
    guarded = _guard(request, db)
    if guarded:
        return guarded
    error = _validate_did(db, did_number)
    if not error:
        error = _validate_destination(open_destination_type, open_destination_target)
    if not error:
        error = _validate_destination(closed_destination_type, closed_destination_target)
    if not error and use_business_hours:
        error = _validate_business_hours(business_days, business_open_time, business_close_time, holiday_dates)
    if error:
        return _render_form(request, db, error=error, status_code=400)
    route = _assign_route(
        InboundRoute(),
        name,
        did_number,
        use_business_hours,
        business_days,
        business_open_time,
        business_close_time,
        holiday_dates,
        open_destination_type,
        open_destination_target,
        closed_destination_type,
        closed_destination_target,
    )
    db.add(route)
    db.commit()
    return RedirectResponse(_safe_next(next_url, "/inbound"), status_code=303)


@router.post("/{route_id}")
def update_inbound_route(
    route_id: int,
    request: Request,
    name: str = Form("Route entrante"),
    did_number: str = Form(""),
    open_destination_type: str = Form("extension"),
    open_destination_target: str = Form(""),
    closed_destination_type: str = Form("hangup"),
    closed_destination_target: str = Form(""),
    use_business_hours: bool = Form(False),
    business_days: list[str] = Form([]),
    business_open_time: str = Form("09:00"),
    business_close_time: str = Form("18:00"),
    holiday_dates: str = Form(""),
    db: Session = Depends(get_db),
):
    guarded = _guard(request, db)
    if guarded:
        return guarded
    route = db.get(InboundRoute, route_id)
    if not route:
        return RedirectResponse("/settings?tab=inbound", status_code=303)
    error = _validate_did(db, did_number, route_id=route.id)
    if not error:
        error = _validate_destination(open_destination_type, open_destination_target)
    if not error:
        error = _validate_destination(closed_destination_type, closed_destination_target)
    if not error and use_business_hours:
        error = _validate_business_hours(business_days, business_open_time, business_close_time, holiday_dates)
    if error:
        return _render_edit_form(request, db, route, error=error, status_code=400)

    _assign_route(
        route,
        name,
        did_number,
        use_business_hours,
        business_days,
        business_open_time,
        business_close_time,
        holiday_dates,
        open_destination_type,
        open_destination_target,
        closed_destination_type,
        closed_destination_target,
    )
    db.add(route)
    db.commit()
    return RedirectResponse("/settings?tab=inbound", status_code=303)


@router.post("/{route_id}/delete")
def delete_inbound_route(
    route_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    guarded = _guard(request, db)
    if guarded:
        return guarded
    route = db.get(InboundRoute, route_id)
    if route:
        db.delete(route)
        db.commit()
    return RedirectResponse("/settings?tab=inbound", status_code=303)


def _assign_route(
    route: InboundRoute,
    name: str,
    did_number: str,
    use_business_hours: bool,
    business_days: list[str],
    business_open_time: str,
    business_close_time: str,
    holiday_dates: str,
    open_destination_type: str,
    open_destination_target: str,
    closed_destination_type: str,
    closed_destination_target: str,
) -> InboundRoute:
    route.name = name.strip() or "Route entrante"
    route.did_number = did_number.strip() or None
    route.use_business_hours = use_business_hours
    route.business_days = ",".join(day for day in BUSINESS_DAYS if day in set(business_days)) or "mon,tue,wed,thu,fri"
    route.business_open_time = business_open_time
    route.business_close_time = business_close_time
    route.holiday_dates = _clean_holiday_dates(holiday_dates) or None
    route.open_destination_type = open_destination_type
    route.open_destination_target = open_destination_target.strip() or None
    route.closed_destination_type = closed_destination_type
    route.closed_destination_target = closed_destination_target.strip() or None
    return route


def _validate_did(db: Session, did_number: str, route_id: int | None = None) -> str | None:
    did_number = did_number.strip()
    if did_number and not DID_RE.match(did_number):
        return "Le numero appele doit contenir 2 a 20 chiffres."
    query = select(InboundRoute.id)
    if did_number:
        query = query.where(InboundRoute.did_number == did_number)
    else:
        query = query.where(InboundRoute.did_number.is_(None))
    if route_id is not None:
        query = query.where(InboundRoute.id != route_id)
    if db.scalar(query):
        if did_number:
            return "Une route existe deja pour ce numero appele."
        return "Une seule route par defaut sans numero appele est possible."
    return None


def _validate_destination(destination_type: str, target: str) -> str | None:
    if destination_type not in DESTINATION_TYPES:
        return "Type de destination invalide."
    if destination_type != "hangup" and not target.strip():
        return "La cible est obligatoire pour cette destination."
    return None


def _validate_business_hours(days: list[str], open_time: str, close_time: str, holiday_dates: str) -> str | None:
    selected_days = [day for day in days if day in BUSINESS_DAYS]
    if not selected_days:
        return "Choisissez au moins un jour ouvert."
    if not TIME_RE.match(open_time) or not TIME_RE.match(close_time):
        return "Les horaires doivent etre au format HH:MM."
    if open_time >= close_time:
        return "L'heure d'ouverture doit etre avant l'heure de fermeture."
    invalid_dates = [date for date in _holiday_date_items(holiday_dates) if not DATE_RE.match(date)]
    if invalid_dates:
        return "Les fermetures exceptionnelles doivent etre au format AAAA-MM-JJ."
    return None


def _clean_holiday_dates(value: str) -> str:
    return "\n".join(_holiday_date_items(value))


def _holiday_date_items(value: str) -> list[str]:
    raw_items = value.replace(",", "\n").splitlines()
    return [item.strip() for item in raw_items if item.strip()]


def _render_form(
    request: Request,
    db: Session,
    error: str | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    routes = list(db.scalars(select(InboundRoute).order_by(InboundRoute.did_number.is_(None).desc(), InboundRoute.did_number, InboundRoute.id)))
    route = None
    return templates.TemplateResponse(
        "inbound/form.html",
        _form_context(request, db, route, routes, error),
        status_code=status_code,
    )


def _render_edit_form(
    request: Request,
    db: Session,
    route: InboundRoute,
    error: str | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    return templates.TemplateResponse(
        "inbound/edit.html",
        _form_context(request, db, route, [], error),
        status_code=status_code,
    )


def _form_context(
    request: Request,
    db: Session,
    route: InboundRoute | None,
    routes: list[InboundRoute],
    error: str | None = None,
) -> dict:
    extensions = list(db.scalars(select(Extension).where(Extension.enabled.is_(True)).order_by(Extension.number)))
    ring_groups = list(db.scalars(select(RingGroup).order_by(RingGroup.number)))
    ivr_menus = list(db.scalars(select(IvrMenu).where(IvrMenu.enabled.is_(True)).order_by(IvrMenu.number)))
    return {
        "request": request,
        "route": route,
        "routes": routes,
        "extensions": extensions,
        "ring_groups": ring_groups,
        "ivr_menus": ivr_menus,
        "business_days": BUSINESS_DAYS,
        "business_day_labels": {
            "mon": "Lundi",
            "tue": "Mardi",
            "wed": "Mercredi",
            "thu": "Jeudi",
            "fri": "Vendredi",
            "sat": "Samedi",
            "sun": "Dimanche",
        },
        "error": error,
    }


def _safe_next(next_url: str, fallback: str) -> str:
    return next_url if next_url.startswith("/") and not next_url.startswith("//") else fallback
