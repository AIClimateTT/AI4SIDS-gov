from fastapi import FastAPI

from app.api.meta import router as meta_router


def create_app() -> FastAPI:
    app = FastAPI(title="DMCU Reporting API")
    app.include_router(meta_router)
    return app


app = create_app()
