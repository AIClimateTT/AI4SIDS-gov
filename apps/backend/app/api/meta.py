from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.contracts import MetricSpec
from app.core.registry import list_modules
from app.core.template_store import list_latest_templates
from app.db import get_session

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
    version: int
    title: str
    description: str
    params: list[TemplateParamInfo]


@router.get("/templates", response_model=list[TemplateInfo])
def get_templates(session: Session = Depends(get_session)) -> list[TemplateInfo]:
    return [
        TemplateInfo(
            name=t.name,
            version=t.version,
            title=t.title,
            description=t.description,
            params=[TemplateParamInfo(name=p.name, required=p.required) for p in t.params],
        )
        for t in list_latest_templates(session)
    ]
