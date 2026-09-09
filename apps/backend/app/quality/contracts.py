from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class CompletenessScore(BaseModel):
    expected: list[str]
    present: list[str]
    missing: list[str]
    rate: float


class NumericalMatch(BaseModel):
    metric: str
    cid: str
    expected: float | str
    appeared: bool
    matched: bool


class NumericalScore(BaseModel):
    items: list[NumericalMatch]
    rate: float
    passed: bool


class CitationProxy(BaseModel):
    citation_instances: int
    missing: int
    misattributed: int
    invented: int
    rate: float


class ClaimRecord(BaseModel):
    claim_id: str
    sentence: str
    cited_cids: list[str]
    number_tokens: list[str]
    critical: bool
    auto_verdict: Literal["supported", "unsupported", "pending_semantic"]
    human_verdict: Literal["supported", "unsupported"] | None = None


class ClaimScore(BaseModel):
    claims: list[ClaimRecord]
    material_count: int
    unsupported_count: int
    critical_unsupported_count: int
    faithfulness_rate: float | None
    unsupported_rate: float | None
    critical_hallucination_rate: float | None


class QualityEval(BaseModel):
    scored_at: datetime
    scorer_version: int = 1
    completeness: CompletenessScore
    numerical: NumericalScore
    citations: CitationProxy
    claims: ClaimScore
