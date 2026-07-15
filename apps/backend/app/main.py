from fastapi import FastAPI

from app.api.meta import router as meta_router
from app.core.registry import register_module
from app.modules.survey123.module import survey123_module


def create_app() -> FastAPI:
    app = FastAPI(title="DMCU Reporting API")
    app.include_router(meta_router)
    register_module(survey123_module)
    return app


app = create_app()
