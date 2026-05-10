from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.csrf import CSRF_SESSION_KEY, csrf_input


def _config_context(request: Request) -> dict[str, object]:
    csrf_token = request.session.get(CSRF_SESSION_KEY, "")
    base_context = {"csrf_token": csrf_token, "csrf_input": csrf_input(csrf_token) if csrf_token else ""}
    if not request.session.get("admin_user_id"):
        return {**base_context, "config_state": None}

    from app.config import get_settings
    from app.database import SessionLocal
    from app.services.config_state import get_config_state

    with SessionLocal() as db:
        try:
            return {**base_context, "config_state": get_config_state(db, get_settings())}
        except Exception:
            return {**base_context, "config_state": None}


class MiniPBXTemplates:
    def __init__(self) -> None:
        self._templates = Jinja2Templates(
            directory=str(Path(__file__).resolve().parent / "templates"),
            context_processors=[_config_context],
        )

    def TemplateResponse(self, name: str, context: dict[str, Any], **kwargs):
        return self._templates.TemplateResponse(context["request"], name, context, **kwargs)


templates = MiniPBXTemplates()
