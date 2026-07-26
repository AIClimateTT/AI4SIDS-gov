from fastapi import APIRouter
from pydantic import BaseModel

from app.core.contracts import MetricSpec
from app.core.registry import list_modules

router = APIRouter()


class ModuleInfo(BaseModel):
    name: str
    metrics: list[MetricSpec]


@router.get("/modules", response_model=list[ModuleInfo])
def get_modules() -> list[ModuleInfo]:
    return [ModuleInfo(name=module.name, metrics=module.list_metrics()) for module in list_modules()]
