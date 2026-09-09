from app.quality.denominators import CRITICAL_METRICS, NAMED_WORKFLOWS, THRESHOLDS, WORD_NUMBERS


def test_critical_metrics_are_the_spec_set():
    assert CRITICAL_METRICS == frozenset(
        {
            "casualty_summary",
            "incident_count",
            "homes_affected_count",
            "estimated_damage_total",
            "special_needs_count",
            "incident_register",
        }
    )


def test_fifteen_is_a_word_number():
    assert WORD_NUMBERS["fifteen"] == 15.0


def test_named_workflows_match_the_spec():
    assert NAMED_WORKFLOWS == (
        "corp_capture_issue",
        "dmu_generate_report",
        "whatsapp_briefing",
        "survey123_ingest",
    )


def test_thresholds_match_the_pm_message():
    assert THRESHOLDS.faithfulness == 0.90
    assert THRESHOLDS.critical_numerical == 1.0
    assert THRESHOLDS.citation_accuracy == 0.95
    assert THRESHOLDS.completeness == 0.95
    assert THRESHOLDS.critical_hallucination == 0.0
    assert THRESHOLDS.unsupported_claim == 0.05
    assert THRESHOLDS.task_completion == 0.80
    assert THRESHOLDS.workflow_reliability == 0.95
    assert THRESHOLDS.usability_mean == 4.0
    assert THRESHOLDS.usability_positive == 0.80
