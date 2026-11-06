from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.dependencies import require_dmu_workspace
from app.core.contracts import MetricSpec
from app.core.registry import list_modules

router = APIRouter()


class ModuleInfo(BaseModel):
    name: str
    metrics: list[MetricSpec]


@router.get("/healthcheck")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@router.get(
    "/modules",
    response_model=list[ModuleInfo],
    dependencies=[Depends(require_dmu_workspace)],
)
def get_modules() -> list[ModuleInfo]:
    return [ModuleInfo(name=module.name, metrics=module.list_metrics()) for module in list_modules()]
