from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.csrf import CSRFMiddleware
from app.database import init_db
from app.routes import auth, backups, calls, config, dashboard, diagnostics, extensions, health, inbound, ivr, monitoring, outbound, ring_groups, settings as settings_routes, trunk, voicemail
from app.services.ami import start_ami_client


def create_app() -> FastAPI:
    settings = get_settings()
    settings.validate_runtime()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.generated_config_dir.mkdir(parents=True, exist_ok=True)
    settings.prompt_dir.mkdir(parents=True, exist_ok=True)
    settings.backup_dir.mkdir(parents=True, exist_ok=True)
    init_db()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.ami_task = start_ami_client(settings)
        try:
            yield
        finally:
            if app.state.ami_task:
                app.state.ami_task.cancel()

    app = FastAPI(title="MiniPBX", lifespan=lifespan)

    app.add_middleware(CSRFMiddleware, enabled=settings.csrf_enabled)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        same_site="lax",
        https_only=settings.session_https_only,
        max_age=settings.session_max_age_seconds,
    )
    app.mount("/static", StaticFiles(directory=str(Path(__file__).resolve().parent / "static")), name="static")
    app.include_router(auth.router)
    app.include_router(extensions.router)
    app.include_router(ring_groups.router)
    app.include_router(ivr.router)
    app.include_router(settings_routes.router)
    app.include_router(health.router)
    app.include_router(inbound.router)
    app.include_router(monitoring.router)
    app.include_router(voicemail.router)
    app.include_router(outbound.router)
    app.include_router(calls.router)
    app.include_router(diagnostics.router)
    app.include_router(backups.router)
    app.include_router(trunk.router)
    app.include_router(config.router)
    app.include_router(dashboard.router)
    return app


app = create_app()
