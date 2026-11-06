from fastapi import APIRouter
from pydantic import BaseModel

from app.core.contracts import Template
from app.core.template_catalog import list_templates

router = APIRouter()


class TemplateParamInfo(BaseModel):
    name: str
    required: bool


class DataRequirementInfo(BaseModel):
    module: str
    metric: str
    params: dict = {}


class NarrationSkillsInfo(BaseModel):
    capture: str = ""
    compose: str


class NarrationInfo(BaseModel):
    identity: str
    skills: NarrationSkillsInfo
    output_sections: list[str]


class RenderInfo(BaseModel):
    format: str = "markdown"
    include_citation_appendix: bool = True
    layout: str = "narrative"


class TemplateSummary(BaseModel):
    name: str
    version: int
    title: str
    description: str
    params: list[TemplateParamInfo]
    data_requirements: list[DataRequirementInfo]
    narration: NarrationInfo


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
            identity=template.narration.identity,
            skills=NarrationSkillsInfo(
                capture=template.narration.skills.capture,
                compose=template.narration.skills.compose,
            ),
            output_sections=template.narration.output_sections,
        ),
    )


@router.get("/templates", response_model=list[TemplateSummary])
def get_templates() -> list[TemplateSummary]:
    return [_template_to_summary(t) for t in list_templates()]
