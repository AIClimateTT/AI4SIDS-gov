from dataclasses import dataclass

CRITICAL_METRICS = frozenset(
    {
        "casualty_summary",
        "incident_count",
        "homes_affected_count",
        "estimated_damage_total",
        "special_needs_count",
        "incident_register",
    }
)

WORD_NUMBERS: dict[str, float] = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
    "hundred": 100,
    "thousand": 1000,
}

NAMED_WORKFLOWS = (
    "corp_capture_issue",
    "dmu_generate_report",
    "whatsapp_briefing",
    "survey123_ingest",
)

ZERO_EVENT_PHRASES = (
    "no casualties",
    "no deaths",
    "no injuries",
    "no one was injured",
    "nobody was injured",
)


@dataclass(frozen=True)
class Thresholds:
    faithfulness: float = 0.90
    critical_numerical: float = 1.0
    citation_accuracy: float = 0.95
    completeness: float = 0.95
    critical_hallucination: float = 0.0
    unsupported_claim: float = 0.05
    task_completion: float = 0.80
    workflow_reliability: float = 0.95
    usability_mean: float = 4.0
    usability_positive: float = 0.80


THRESHOLDS = Thresholds()
