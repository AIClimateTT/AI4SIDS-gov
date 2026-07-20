from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.ingest import router as ingest_router
from app.api.meta import router as meta_router
from app.api.overview import router as overview_router
from app.api.reports import router as reports_router
from app.core.registry import register_module
from app.modules.sitreps.module import sitrep_module
from app.modules.survey123.module import get_survey123_module

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
    app.include_router(overview_router)
    app.include_router(reports_router)
    app.include_router(ingest_router)
    register_module(get_survey123_module())
    register_module(sitrep_module)
    return app


app = create_app()
