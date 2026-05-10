import re

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from app.csrf import CSRFMiddleware


def test_csrf_injects_token_and_blocks_missing_token():
    app = FastAPI()
    app.add_middleware(CSRFMiddleware, enabled=True)
    app.add_middleware(SessionMiddleware, secret_key="test-secret")

    @app.get("/")
    def form():
        return HTMLResponse('<form method="post" action="/save"><button>Save</button></form>')

    @app.post("/save")
    async def save(request: Request):
        form_data = await request.form()
        return PlainTextResponse(form_data["value"])

    client = TestClient(app)
    response = client.get("/")
    token_match = re.search(r'name="csrf_token" value="([^"]+)"', response.text)

    assert token_match
    assert client.post("/save", data={"value": "ok"}).status_code == 403

    saved = client.post("/save", data={"value": "ok", "csrf_token": token_match.group(1)})

    assert saved.status_code == 200
    assert saved.text == "ok"
