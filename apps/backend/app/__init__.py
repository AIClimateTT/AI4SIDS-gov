from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.ingest import router as ingest_router
from app.api.meta import router as meta_router
from app.api.overview import router as overview_router
from app.api.reports import router as reports_router
from app.api.submissions import router as submissions_router
from app.api.templates import router as templates_router
from app.api.whatsapp import router as whatsapp_router
from app.api.capture import router as capture_router
from app.api.users import router as users_router
from app.api.quality import router as quality_router
from app.config import settings, validate_runtime_settings
from app.core.registry import ensure_default_modules_registered


def _cors_origins() -> list[str]:
    origins = [
        settings.app_url,
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    return list(dict.fromkeys(origins))


def create_app() -> FastAPI:
    validate_runtime_settings()
    app = FastAPI(title="DMCU Reporting API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(meta_router)
    app.include_router(templates_router)
    app.include_router(overview_router)
    app.include_router(reports_router)
    app.include_router(ingest_router)
    app.include_router(submissions_router)
    app.include_router(whatsapp_router)
    app.include_router(capture_router)
    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(quality_router)
    ensure_default_modules_registered()
    return app


app = create_app()
