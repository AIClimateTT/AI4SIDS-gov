from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.contracts import (
    DataRequirement,
    NarrationConfig,
    RenderConfig,
    Template,
    TemplateParam,
)
from app.core.template_store import (
    create_template_version,
    get_template_version,
    list_latest_templates,
    list_template_versions,
)
from app.db import get_session

router = APIRouter()


class TemplateParamInfo(BaseModel):
    name: str
    required: bool


class DataRequirementInfo(BaseModel):
    module: str
    metric: str
    params: dict = {}


class NarrationInfo(BaseModel):
    system_prompt: str
    output_sections: list[str]


class RenderInfo(BaseModel):
    format: str = "markdown"
    include_citation_appendix: bool = True


class TemplateSummary(BaseModel):
    name: str
    version: int
    title: str
    description: str
    params: list[TemplateParamInfo]
    data_requirements: list[DataRequirementInfo]
    narration: NarrationInfo


class TemplateVersionSummary(BaseModel):
    name: str
    version: int
    title: str
    created_at: datetime


class CreateTemplateRequest(BaseModel):
    name: str
    title: str
    description: str
    params: list[TemplateParamInfo]
    data_requirements: list[DataRequirementInfo]
    narration: NarrationInfo
    render: RenderInfo = RenderInfo()


def _template_to_summary(template: Template) -> TemplateSummary:
    return TemplateSummary(
        name=template.name,
        version=template.version,
        title=template.title,
        description=template.description,
        params=[TemplateParamInfo(name=p.name, required=p.required) for p in template.params],
        data_requirements=[
            DataRequirementInfo(module=d.module, metric=d.metric, params=d.params)
            for d in template.data_requirements
        ],
        narration=NarrationInfo(
            system_prompt=template.narration.system_prompt,
            output_sections=template.narration.output_sections,
        ),
    )


def _request_to_template(request: CreateTemplateRequest) -> Template:
    return Template(
        name=request.name,
        title=request.title,
        description=request.description,
        params=[TemplateParam(name=p.name, required=p.required) for p in request.params],
        data_requirements=[
            DataRequirement(module=d.module, metric=d.metric, params=d.params)
            for d in request.data_requirements
        ],
        narration=NarrationConfig(
            system_prompt=request.narration.system_prompt,
            output_sections=request.narration.output_sections,
        ),
        render=RenderConfig(
            format=request.render.format,
            include_citation_appendix=request.render.include_citation_appendix,
        ),
    )


@router.get("/templates", response_model=list[TemplateSummary])
def get_templates(session: Session = Depends(get_session)) -> list[TemplateSummary]:
    return [_template_to_summary(t) for t in list_latest_templates(session)]


@router.get("/templates/{name}/versions", response_model=list[TemplateVersionSummary])
def get_template_versions(name: str, session: Session = Depends(get_session)) -> list[TemplateVersionSummary]:
    records = list_template_versions(name, session)
    if not records:
        raise HTTPException(status_code=404, detail=f"unknown template: {name}")
    return [
        TemplateVersionSummary(
            name=record.name,
            version=record.version,
            title=record.title,
            created_at=record.created_at,
        )
        for record in records
    ]


@router.get("/templates/{name}/versions/{version}", response_model=TemplateSummary)
def get_template_by_version(
    name: str, version: int, session: Session = Depends(get_session)
) -> TemplateSummary:
    template = get_template_version(name, version, session)
    if template is None:
        raise HTTPException(status_code=404, detail=f"template not found: {name} v{version}")
    return _template_to_summary(template)


@router.post("/templates", response_model=TemplateSummary, status_code=201)
def create_template(
    request: CreateTemplateRequest, session: Session = Depends(get_session)
) -> TemplateSummary:
    try:
        template = create_template_version(_request_to_template(request), session)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _template_to_summary(template)
