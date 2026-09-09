from app.core.citation_check import (
    CITATION_MARKER_RE,
    NUMBER_TOKEN_RE,
    CitationCheckResult,
    cids_in,
    split_narrative_units,
)
from app.core.citation_check import _strip_dates
from app.core.contracts import FactTable
from app.quality.contracts import ClaimRecord, ClaimScore
from app.quality.denominators import CRITICAL_METRICS, ZERO_EVENT_PHRASES


def _effective_verdict(claim: ClaimRecord) -> str:
    return claim.human_verdict or claim.auto_verdict


def _has_zero_casualty(fact_table: FactTable) -> bool:
    for fact in fact_table.facts:
        if fact.metric != "casualty_summary":
            continue
        if isinstance(fact.value, (int, float)) and float(fact.value) == 0:
            return True
        if fact.breakdown and any(float(value) == 0 for value in fact.breakdown.values()):
            return True
    return False


def recompute_claim_rates(score: ClaimScore) -> ClaimScore:
    resolved = [
        claim
        for claim in score.claims
        if _effective_verdict(claim) != "pending_semantic"
    ]
    unsupported = [
        claim for claim in resolved if _effective_verdict(claim) == "unsupported"
    ]
    supported = [
        claim for claim in resolved if _effective_verdict(claim) == "supported"
    ]
    critical = [claim for claim in score.claims if claim.critical]
    critical_unsupported = [
        claim for claim in critical if _effective_verdict(claim) == "unsupported"
    ]
    faithfulness = None if not resolved else len(supported) / len(resolved)
    unsupported_rate = None if not resolved else len(unsupported) / len(resolved)
    if not critical:
        hallucination = None
    else:
        hallucination = len(critical_unsupported) / len(critical)
    return score.model_copy(
        update={
            "material_count": len(score.claims),
            "unsupported_count": len(unsupported),
            "critical_unsupported_count": len(critical_unsupported),
            "faithfulness_rate": faithfulness,
            "unsupported_rate": unsupported_rate,
            "critical_hallucination_rate": hallucination,
        }
    )


def extract_claims(
    narrative: str, fact_table: FactTable, result: CitationCheckResult
) -> ClaimScore:
    valid_cids = {fact.citation.cid for fact in fact_table.facts}
    facts_by_cid = {fact.citation.cid: fact for fact in fact_table.facts}
    claims: list[ClaimRecord] = []
    index = 0
    for sentence in split_narrative_units(narrative):
        cited = sorted(cids_in(sentence) & valid_cids)
        stripped = _strip_dates(CITATION_MARKER_RE.sub("", sentence))
        tokens = NUMBER_TOKEN_RE.findall(stripped)
        zero_event = any(phrase in sentence.lower() for phrase in ZERO_EVENT_PHRASES)
        if not tokens and not cited and not zero_event:
            continue
        index += 1
        cited_facts = [facts_by_cid[cid] for cid in cited if cid in facts_by_cid]
        critical = (
            any(fact.metric in CRITICAL_METRICS for fact in cited_facts) or zero_event
        )
        related = [
            violation
            for violation in result.violations
            if violation.kind != "empty_narrative" and violation.sentence == sentence
        ]
        if related:
            verdict: str = "unsupported"
        elif zero_event and not _has_zero_casualty(fact_table):
            verdict = "unsupported"
        elif tokens and cited:
            if cited_facts and all(fact.verification == "pending" for fact in cited_facts):
                verdict = "pending_semantic"
            else:
                verdict = "supported"
        else:
            verdict = "pending_semantic"
        claims.append(
            ClaimRecord(
                claim_id=f"cl{index:03d}",
                sentence=sentence,
                cited_cids=cited,
                number_tokens=tokens,
                critical=critical,
                auto_verdict=verdict,  # type: ignore[arg-type]
            )
        )
    return recompute_claim_rates(
        ClaimScore(
            claims=claims,
            material_count=0,
            unsupported_count=0,
            critical_unsupported_count=0,
            faithfulness_rate=None,
            unsupported_rate=None,
            critical_hallucination_rate=None,
        )
    )
