from fastapi import APIRouter
from pydantic import BaseModel

from app.core.contracts import MetricSpec
from app.core.registry import list_modules, list_templates

router = APIRouter()


class ModuleInfo(BaseModel):
    name: str
    metrics: list[MetricSpec]


@router.get("/modules", response_model=list[ModuleInfo])
def get_modules() -> list[ModuleInfo]:
    return [ModuleInfo(name=module.name, metrics=module.list_metrics()) for module in list_modules()]


class TemplateParamInfo(BaseModel):
    name: str
    required: bool


class TemplateInfo(BaseModel):
    name: str
    title: str
    description: str
    params: list[TemplateParamInfo]


@router.get("/templates", response_model=list[TemplateInfo])
def get_templates() -> list[TemplateInfo]:
    return [
        TemplateInfo(
            name=t.name,
            title=t.title,
            description=t.description,
            params=[TemplateParamInfo(name=p.name, required=p.required) for p in t.params],
        )
        for t in list_templates()
    ]
