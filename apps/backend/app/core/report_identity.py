"""What a person calls a report: its kind, title and period.

Derived from the stored row, so reports made before this existed read the same
way as new ones.
"""

from datetime import date
from typing import Literal

from app.core.renderer import strip_citation_markup
from app.core.report_models import Report
from app.modules.survey123.normalize import CORPORATION_LABELS

ReportKind = Literal["corporation", "minister", "survey123", "other"]

KIND_TEMPLATES: dict[str, tuple[str, ...]] = {
    "corporation": ("corp_situation_report",),
    "minister": ("minister_situation_report",),
    "survey123": ("survey123_summary", "field_data_region_review"),
}

# Reports from the database-template era carry version numbers below this; YAML
# templates start here. Their figures were not produced by the current rules.
CURRENT_FORMAT_VERSION = 100


def report_kind(template: str) -> ReportKind:
    for kind, templates in KIND_TEMPLATES.items():
        if template in templates:
            return kind  # type: ignore[return-value]
    return "other"


def _corporation_label(params: dict) -> str | None:
    corporation = params.get("corporation")
    if not corporation:
        return None
    return CORPORATION_LABELS.get(corporation, str(corporation))


def report_title(template: str, params: dict, report_number: int | None) -> str:
    kind = report_kind(template)
    corporation = _corporation_label(params)
    if kind == "corporation":
        if not corporation:
            return "Corporation report"
        suffix = f" #{report_number}" if report_number else ""
        return f"{corporation} report{suffix}"
    if kind == "minister":
        return "Minister report"
    if kind == "survey123":
        return f"Survey123 summary: {corporation}" if corporation else "Survey123 summary"
    if template == "whatsapp_hour_briefing":
        return "WhatsApp briefing"
    return template.replace("_", " ").strip().capitalize()


def _day(value: object) -> date | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _format_day(value: date, *, year: bool = True) -> str:
    text = f"{value.day} {value:%b}"
    return f"{text} {value.year}" if year else text


def report_period(params: dict) -> str | None:
    start = _day(params.get("date_from"))
    end = _day(params.get("date_to"))
    if start and end:
        if start == end:
            return _format_day(start)
        return f"{_format_day(start, year=start.year != end.year)} – {_format_day(end)}"
    if start:
        return f"From {_format_day(start)}"
    if end:
        return f"To {_format_day(end)}"
    return None


def clean_markdown(row: Report) -> str:
    return row.final_markdown or strip_citation_markup(row.markdown or "")


def identity_fields(row: Report) -> dict:
    params = row.params or {}
    number = ((row.fact_table or {}).get("params") or {}).get("report_number")
    kind = report_kind(row.template)
    return {
        "kind": kind,
        "title": report_title(row.template, params, number),
        "period": report_period(params),
        "verified": kind == "survey123",
        "older_format": row.template_version < CURRENT_FORMAT_VERSION,
    }
