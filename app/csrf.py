import html
import re
import secrets
from collections.abc import Awaitable, Callable
from urllib.parse import parse_qs

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.types import ASGIApp

CSRF_SESSION_KEY = "csrf_token"
CSRF_FIELD_NAME = "csrf_token"
CSRF_HEADER_NAME = "x-csrf-token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class CSRFMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, *, enabled: bool = True) -> None:
        super().__init__(app)
        self.enabled = enabled

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if not self.enabled:
            return await call_next(request)

        token = request.session.get(CSRF_SESSION_KEY)
        if not token:
            token = secrets.token_urlsafe(32)
            request.session[CSRF_SESSION_KEY] = token

        if request.method not in SAFE_METHODS:
            body = await request.body()
            _replay_body(request, body)
            submitted = _submitted_token(request, body)
            if not submitted or not secrets.compare_digest(submitted, token):
                return PlainTextResponse("Jeton CSRF invalide.", status_code=403)

        response = await call_next(request)
        return await _inject_csrf_token(response, token)


def csrf_input(token: str) -> str:
    escaped = html.escape(token, quote=True)
    return f'<input type="hidden" name="{CSRF_FIELD_NAME}" value="{escaped}">'


def _submitted_token(request: Request, body: bytes) -> str:
    header_token = request.headers.get(CSRF_HEADER_NAME)
    if header_token:
        return header_token

    content_type = request.headers.get("content-type", "")
    if "application/x-www-form-urlencoded" in content_type:
        parsed = parse_qs(body.decode("utf-8", errors="ignore"))
        values = parsed.get(CSRF_FIELD_NAME) or []
        return values[0] if values else ""
    if "multipart/form-data" in content_type:
        match = re.search(
            rb'name="' + CSRF_FIELD_NAME.encode("ascii") + rb'"\r?\n\r?\n([^\r\n]+)',
            body,
        )
        return match.group(1).decode("utf-8", errors="ignore") if match else ""
    return ""


def _replay_body(request: Request, body: bytes) -> None:
    async def receive() -> dict:
        return {"type": "http.request", "body": body, "more_body": False}

    request._receive = receive  # noqa: SLF001 - Starlette has no public body replay hook.


async def _inject_csrf_token(response: Response, token: str) -> Response:
    content_type = response.headers.get("content-type", "")
    if "text/html" not in content_type:
        return response

    body = b""
    async for chunk in response.body_iterator:
        body += chunk
    text = body.decode(response.charset or "utf-8", errors="replace")
    hidden = csrf_input(token)
    text = re.sub(
        r'(<form\b[^>]*\bmethod=["\']post["\'][^>]*>)',
        lambda match: match.group(1) + hidden,
        text,
        flags=re.IGNORECASE,
    )

    headers = dict(response.headers)
    headers.pop("content-length", None)
    return Response(
        text,
        status_code=response.status_code,
        headers=headers,
        media_type=response.media_type,
        background=response.background,
    )
