from pathlib import Path

from fastapi import FastAPI

from app.api.meta import router as meta_router
from app.core.registry import register_module, register_template
from app.modules.survey123.module import survey123_module
from app.templates.loader import load_templates_from_directory

TEMPLATES_DIR = Path(__file__).parent / "templates" / "definitions"


def create_app() -> FastAPI:
    app = FastAPI(title="DMCU Reporting API")
    app.include_router(meta_router)
    register_module(survey123_module)
    for template in load_templates_from_directory(TEMPLATES_DIR):
        register_template(template)
    return app


app = create_app()
