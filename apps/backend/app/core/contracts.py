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


class FactTable(BaseModel):
    request_id: str
    template: str
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
