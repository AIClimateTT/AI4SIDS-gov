from datetime import datetime, timezone

from app.core.citation_check import CitationCheckResult
from app.core.contracts import FactTable, Template
from app.quality.claims import extract_claims
from app.quality.citations import score_citations
from app.quality.completeness import score_completeness
from app.quality.contracts import QualityEval
from app.quality.numerical import score_numerical


def score_quality(
    template: Template,
    fact_table: FactTable,
    narrative: str,
    markdown: str,
    result: CitationCheckResult,
) -> QualityEval:
    return QualityEval(
        scored_at=datetime.now(timezone.utc),
        completeness=score_completeness(template, fact_table, markdown),
        numerical=score_numerical(fact_table, markdown, result),
        citations=score_citations(result, narrative),
        claims=extract_claims(narrative, fact_table, result),
    )
