from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.ingest import router as ingest_router
from app.api.meta import router as meta_router
from app.api.overview import router as overview_router
from app.api.reports import router as reports_router
from app.api.templates import router as templates_router
from app.core.registry import ensure_default_modules_registered

CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]


def create_app() -> FastAPI:
    app = FastAPI(title="DMCU Reporting API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(meta_router)
    app.include_router(templates_router)
    app.include_router(overview_router)
    app.include_router(reports_router)
    app.include_router(ingest_router)
    ensure_default_modules_registered()
    return app


app = create_app()
