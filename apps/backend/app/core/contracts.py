from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class Citation(BaseModel):
    cid: str
    module: str
    description: str
    query_ref: str
    record_ids: list[str] | None
    as_of: datetime


class Fact(BaseModel):
    metric: str
    value: int | float | str
    unit: str | None
    scope: dict[str, str]
    breakdown: dict[str, int | float] | None
    verification: Literal["validated", "pending", "mixed", "n/a"]
    citation: Citation
    gaps: list[str] = []
    """Caveats a metric discovered about its own rows (e.g. rows whose incident
    type the normaliser could not place, which the selection predicate then
    silently drops). assemble_fact_table hoists these into FactTable.gaps,
    which is where the narration prompt tells the model to look."""


class FactTable(BaseModel):
    request_id: str
    template: str
    template_version: int = 1
    params: dict
    generated_at: datetime
    facts: list[Fact]
    gaps: list[str]


class MetricSpec(BaseModel):
    name: str
    description: str
    params_schema: dict
    module: str


class IngestResult(BaseModel):
    rows_read: int
    rows_inserted: int
    rows_updated: int
    duplicates_flagged: int
    unmapped_values: dict[str, list[str]]
    pii_columns_dropped: list[str]


class TemplateParam(BaseModel):
    name: str
    required: bool = False


class DataRequirement(BaseModel):
    module: str
    metric: str
    params: dict = {}


class NarrationConfig(BaseModel):
    system_prompt: str
    output_sections: list[str]


class RenderConfig(BaseModel):
    format: Literal["markdown"] = "markdown"
    include_citation_appendix: bool = True


class Template(BaseModel):
    name: str
    version: int = 1
    title: str
    description: str
    params: list[TemplateParam]
    data_requirements: list[DataRequirement]
    narration: NarrationConfig
    render: RenderConfig


class RowErrorInfo(BaseModel):
    file: Literal["incidents", "logs"]
    row_number: int
    """The spreadsheet row number as the corp officer sees it in their file
    (header is row 1, so the first data row is row 2), not a zero- or
    one-indexed offset into the data rows."""
    reason: str


class SubmissionIngestResult(BaseModel):
    submission_id: int
    sequence_no: int
    incidents_read: int
    incidents_inserted: int
    incidents_updated: int
    logs_read: int
    logs_inserted: int
    row_errors: list[RowErrorInfo]
    unmapped_values: dict[str, list[str]]
    pii_columns_dropped: list[str]
