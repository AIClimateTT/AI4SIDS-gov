from fastapi import FastAPI

from app.api.ingest import router as ingest_router
from app.api.meta import router as meta_router
from app.api.reports import router as reports_router
from app.core.registry import register_module
from app.modules.survey123.module import get_survey123_module


def create_app() -> FastAPI:
    app = FastAPI(title="DMCU Reporting API")
    app.include_router(meta_router)
    app.include_router(reports_router)
    app.include_router(ingest_router)
    register_module(get_survey123_module())
    return app


app = create_app()
