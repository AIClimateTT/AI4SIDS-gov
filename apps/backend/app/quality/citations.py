from app.core.citation_check import CITATION_MARKER_RE, CitationCheckResult
from app.quality.contracts import CitationProxy


def score_citations(result: CitationCheckResult, narrative: str) -> CitationProxy:
    markers = CITATION_MARKER_RE.findall(narrative)
    citation_instances = len(markers)
    missing = sum(1 for v in result.violations if v.kind == "missing_citation")
    misattributed = sum(1 for v in result.violations if v.kind == "misattributed_number")
    invented = sum(1 for v in result.violations if v.kind == "invented_number")
    total = citation_instances + missing
    failed = missing + misattributed
    rate = 1.0 if total == 0 else max(0.0, 1.0 - failed / total)
    return CitationProxy(
        citation_instances=citation_instances,
        missing=missing,
        misattributed=misattributed,
        invented=invented,
        rate=rate,
    )
