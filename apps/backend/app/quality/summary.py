from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.report_models import Report
from app.quality.contracts import QualityEval
from app.quality.denominators import THRESHOLDS
from app.quality.models import ReportRating, WorkflowEvent


class ThresholdStatus(BaseModel):
    name: str
    threshold: float
    actual: float | None
    met: bool | None
    sample: int


class QualitySummary(BaseModel):
    report_count: int
    scored_count: int
    thresholds: list[ThresholdStatus]
    rating_count: int = 0
    rating_mean: float | None = None
    rating_positive_rate: float | None = None
    task_started: int = 0
    task_succeeded_unaided: int = 0


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _met_gte(actual: float | None, threshold: float) -> bool | None:
    if actual is None:
        return None
    return actual >= threshold


def _met_lte(actual: float | None, threshold: float) -> bool | None:
    if actual is None:
        return None
    return actual <= threshold


def build_quality_summary(session: Session) -> QualitySummary:
    report_count = session.scalar(select(func.count()).select_from(Report)) or 0
    rows = list(session.scalars(select(Report).where(Report.quality_eval.is_not(None))).all())
    evals = [QualityEval.model_validate(row.quality_eval) for row in rows]

    faithfulness = _mean(
        [item.claims.faithfulness_rate for item in evals if item.claims.faithfulness_rate is not None]
    )
    citation = _mean([item.citations.rate for item in evals])
    numerical_pass = _mean([1.0 if item.numerical.passed else 0.0 for item in evals])
    completeness = _mean([item.completeness.rate for item in evals])
    hallucination = _mean(
        [
            item.claims.critical_hallucination_rate
            for item in evals
            if item.claims.critical_hallucination_rate is not None
        ]
    )
    unsupported = _mean(
        [item.claims.unsupported_rate for item in evals if item.claims.unsupported_rate is not None]
    )

    started = (
        session.scalar(
            select(func.count())
            .select_from(WorkflowEvent)
            .where(WorkflowEvent.outcome == "started")
        )
        or 0
    )
    unaided = (
        session.scalar(
            select(func.count())
            .select_from(WorkflowEvent)
            .where(
                WorkflowEvent.outcome == "succeeded",
                WorkflowEvent.assisted.is_(False),
            )
        )
        or 0
    )
    task_rate = None if started == 0 else unaided / started

    ratings = list(session.scalars(select(ReportRating)).all())
    rating_count = len(ratings)
    rating_mean = _mean([float(row.rating) for row in ratings])
    positive = _mean([1.0 if row.rating >= 4 else 0.0 for row in ratings])

    scored = len(evals)
    thresholds = [
        ThresholdStatus(
            name="faithfulness",
            threshold=THRESHOLDS.faithfulness,
            actual=faithfulness,
            met=_met_gte(faithfulness, THRESHOLDS.faithfulness),
            sample=scored,
        ),
        ThresholdStatus(
            name="critical_numerical",
            threshold=THRESHOLDS.critical_numerical,
            actual=numerical_pass,
            met=_met_gte(numerical_pass, THRESHOLDS.critical_numerical),
            sample=scored,
        ),
        ThresholdStatus(
            name="citation_accuracy",
            threshold=THRESHOLDS.citation_accuracy,
            actual=citation,
            met=_met_gte(citation, THRESHOLDS.citation_accuracy),
            sample=scored,
        ),
        ThresholdStatus(
            name="completeness",
            threshold=THRESHOLDS.completeness,
            actual=completeness,
            met=_met_gte(completeness, THRESHOLDS.completeness),
            sample=scored,
        ),
        ThresholdStatus(
            name="critical_hallucination",
            threshold=THRESHOLDS.critical_hallucination,
            actual=hallucination,
            met=_met_lte(hallucination, THRESHOLDS.critical_hallucination),
            sample=scored,
        ),
        ThresholdStatus(
            name="unsupported_claim",
            threshold=THRESHOLDS.unsupported_claim,
            actual=unsupported,
            met=_met_lte(unsupported, THRESHOLDS.unsupported_claim),
            sample=scored,
        ),
        ThresholdStatus(
            name="task_completion",
            threshold=THRESHOLDS.task_completion,
            actual=task_rate,
            met=_met_gte(task_rate, THRESHOLDS.task_completion),
            sample=started,
        ),
        ThresholdStatus(
            name="usability_mean",
            threshold=THRESHOLDS.usability_mean,
            actual=rating_mean,
            met=_met_gte(rating_mean, THRESHOLDS.usability_mean),
            sample=rating_count,
        ),
        ThresholdStatus(
            name="usability_positive",
            threshold=THRESHOLDS.usability_positive,
            actual=positive,
            met=_met_gte(positive, THRESHOLDS.usability_positive),
            sample=rating_count,
        ),
    ]
    return QualitySummary(
        report_count=report_count,
        scored_count=scored,
        thresholds=thresholds,
        rating_count=rating_count,
        rating_mean=rating_mean,
        rating_positive_rate=positive,
        task_started=started,
        task_succeeded_unaided=unaided,
    )
