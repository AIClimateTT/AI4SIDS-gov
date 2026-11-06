import re
from datetime import datetime

from app.core.contracts import FactTable, Template
from app.core.localtime import to_local
from app.modules.survey123.normalize import CORPORATION_LABELS

# Matches the [C001] markers the composer is told to emit, plus any space
# ahead of them, so stripping "injured [C005]." leaves "injured." not
# "injured ." — the final variant is prose a reader sees, not a QC view.
HAZARD_TITLES = {
    "adverse_weather": "ADVERSE WEATHER",
    "flood": "FLOOD",
    "landslide": "LANDSLIDE",
    "wind": "HIGH WIND",
    "fire": "FIRE",
    "other": "",
}
MINISTRY_NAME = "Ministry of Rural Development and Local Government"
MINISTRY_LOCATION = f"{MINISTRY_NAME}, Kent House"

_CITATION_MARKER = re.compile(r"[ \t]*\[C\d{3}\]")


def _strip_citations(text: str) -> str:
    return _CITATION_MARKER.sub("", text)


_APPENDIX_HEADING = re.compile(r"^## Citation Appendix\s*$", re.MULTILINE)
_TABLE_SEP_CELL = re.compile(r"^:?-{3,}:?$")


def strip_citation_appendix(markdown: str) -> str:
    """Drop the markdown appendix; the draft fact table already lists the same facts."""
    match = _APPENDIX_HEADING.search(markdown)
    if match is None:
        return markdown
    start = match.start()
    after = markdown[match.end() :]
    next_heading = re.search(r"^## ", after, re.MULTILINE)
    end = match.end() + next_heading.start() if next_heading else len(markdown)
    return markdown[:start].rstrip() + markdown[end:]


def _table_cells(line: str) -> list[str] | None:
    stripped = line.strip()
    if not stripped.startswith("|"):
        return None
    return [cell.strip() for cell in stripped.strip("|").split("|")]


def _is_separator_row(cells: list[str]) -> bool:
    return bool(cells) and all(
        _TABLE_SEP_CELL.fullmatch(cell.replace(" ", "")) for cell in cells
    )


def _strip_cite_columns(markdown: str) -> str:
    lines = markdown.split("\n")
    out: list[str] = []
    index = 0
    while index < len(lines):
        cells = _table_cells(lines[index])
        if cells is None:
            out.append(lines[index])
            index += 1
            continue
        cite_at = next(
            (pos for pos, cell in enumerate(cells) if cell.lower() == "cite"),
            None,
        )
        if cite_at is None:
            out.append(lines[index])
            index += 1
            continue
        while index < len(lines):
            row = _table_cells(lines[index])
            if row is None:
                break
            kept = [cell for pos, cell in enumerate(row) if pos != cite_at]
            if not kept:
                index += 1
                continue
            if _is_separator_row(row):
                out.append("|" + "|".join("---" for _ in kept) + "|")
            else:
                out.append("| " + " | ".join(kept) + " |")
            index += 1
    return "\n".join(out)


def strip_citation_markup(markdown: str) -> str:
    """Issued-document cleanup: no appendix, no Cite column, no [Cxxx] pills."""
    return _strip_citations(_strip_cite_columns(strip_citation_appendix(markdown)))


def _citation_appendix_line(citation) -> str:
    return (
        f"- [{citation.cid}] {citation.description} "
        f"(Source query: `{citation.query_ref}`, As of: {citation.as_of})"
    )


def _humanize(slug: str) -> str:
    """Turn a stored slug into label case.

    Officers' type values arrive as slugs ("blown_off_roof") and some carry a
    stray trailing underscore from data entry ("flooding_"), which must not
    reach a filing.
    """
    words = [
        word
        for part in slug.strip().replace("-", "_").split("_")
        for word in part.split()
        if word
    ]
    if not words:
        return slug
    return " ".join(word[0].upper() + word[1:].lower() for word in words)


def _label(value: str) -> str:
    return CORPORATION_LABELS.get(value) or _humanize(value)


def _document_title(template: Template, fact_table: FactTable) -> str:
    if template.render.layout == "filing":
        hazard = HAZARD_TITLES.get(str(fact_table.params.get("hazard_type")), "")
        title = f"{hazard} SITUATION REPORT".strip()
        number = fact_table.params.get("report_number")
        return f"{title} #{number}" if number else title
    corp = fact_table.params.get("corporation")
    if not corp:
        return template.title
    name = _label(str(corp))
    if name.lower() in template.title.lower():
        return template.title
    return f"{template.title} — {name}"


def _place(scope: dict[str, str]) -> str:
    community = (scope.get("community") or "").strip()
    street = (scope.get("street") or "").strip()
    if community and street:
        return f"{community} / {street}"
    return community or street


def _format_number(value: int | float | str) -> str:
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, int):
        return str(value)
    return str(value)


def _md_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    """Render a table, dropping any column that is empty for every row.

    An officer who records no deaths and no action should not be handed a
    filing with two blank columns eating the width.
    """
    if not rows:
        return []
    keep = [
        index
        for index in range(len(headers))
        if any((row[index] or "").strip() for row in rows)
    ]
    if not keep:
        return []
    headers = [headers[index] for index in keep]
    rows = [[row[index] for index in keep] for row in rows]
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")
    return lines


def render_filing(
    template: Template,
    fact_table: FactTable,
    narrative: str,
    *,
    include_citations: bool = True,
) -> str:
    """Render the filing layout, in the order of the corporation baselines.

    With ``include_citations`` the output is the draft an officer checks its
    figures against, gaps included. Without it, the same facts render as the
    document that gets issued: no [Cxxx] markers, no Cite columns, no gaps.
    """
    parts = [f"# {_document_title(template, fact_table)}", ""]

    def cited(cells: list[str], cid: str) -> list[str]:
        return cells + [f"[{cid}]"] if include_citations else cells

    def headers(names: list[str]) -> list[str]:
        return names + ["Cite"] if include_citations else names

    if narrative.strip():
        prose = narrative.strip()
        if not include_citations:
            prose = _strip_citations(prose)
        parts.extend([prose, ""])

    count = next((fact for fact in fact_table.facts if fact.metric == "incident_count"), None)
    if count is not None and count.value and count.breakdown:
        rows = [
            cited([_label(key), _format_number(value)], count.citation.cid)
            for key, value in count.breakdown.items()
            if value
        ]
        if rows:
            parts.extend(["## Situation Summary", ""])
            parts.extend(_md_table(headers(["Type", "Count"]), rows))

    stock = [
        fact
        for fact in fact_table.facts
        if fact.metric == "relief_stock_summary" and fact.value
    ]
    distributed = [fact for fact in stock if fact.scope.get("category") == "relief_distributed"]
    resources = [fact for fact in stock if fact.scope.get("category") != "relief_distributed"]

    def item(fact) -> str:
        return fact.scope.get("item") or fact.scope.get("statement") or ""

    if distributed:
        parts.extend(["## Disaster Relief Distribution Summary", ""])
        rows = [
            cited([item(f), _format_number(f.value), f.unit or ""], f.citation.cid)
            for f in distributed
        ]
        parts.extend(_md_table(headers(["Item", "Quantity", "Unit"]), rows))

    if resources:
        parts.extend(["## Resources", ""])
        rows = [
            cited(
                [
                    item(f),
                    _format_number(f.value),
                    f.unit or "",
                    _humanize(f.scope.get("status") or ""),
                ],
                f.citation.cid,
            )
            for f in resources
        ]
        parts.extend(_md_table(headers(["Item", "Quantity", "Unit", "Status"]), rows))

    activities = [fact for fact in fact_table.facts if fact.metric == "activity_log"]
    if activities:
        parts.extend(["## Summary of Activities", ""])
        for fact in activities:
            marker = f" [{fact.citation.cid}]" if include_citations else ""
            parts.append(f"- {fact.value}{marker}")
        parts.append("")

    register = [fact for fact in fact_table.facts if fact.metric == "incident_register"]
    if register:
        parts.extend(["## Incidents", ""])
        rows = []
        for number, fact in enumerate(register, start=1):
            rows.append(
                cited(
                    [
                        str(number),
                        fact.scope.get("date") or "",
                        _place(fact.scope),
                        _humanize(fact.scope.get("type") or ""),
                        fact.scope.get("summary") or "",
                        fact.scope.get("injuries") or "",
                        fact.scope.get("deaths") or "",
                        fact.scope.get("action") or "",
                    ],
                    fact.citation.cid,
                )
            )
        parts.extend(
            _md_table(
                headers(
                    [
                        "No.",
                        "Date",
                        "Location",
                        "Type",
                        "Description",
                        "Injuries",
                        "Deaths",
                        "Action Taken",
                    ]
                ),
                rows,
            )
        )

    gaps = [
        gap
        for gap in fact_table.gaps
        if gap.strip() and gap.strip().lower() != "none"
    ]
    if gaps and include_citations:
        parts.append("## Data Gaps")
        for gap in gaps:
            parts.append(f"- {gap}")
        parts.append("")

    if include_citations and template.render.include_citation_appendix:
        parts.append("## Citation Appendix")
        for fact in fact_table.facts:
            citation = fact.citation
            parts.append(_citation_appendix_line(citation))
        parts.append("")

    parts.append(
        "No further reports to be submitted."
        if fact_table.params.get("alert_level") == "discontinued"
        else "END OF REPORT"
    )
    return "\n".join(parts) + "\n"


def format_as_at(value: datetime) -> str:
    """The baselines' form: 4:00 pm on 30/06/2023.

    A naive value is the officer's Trinidad wall-clock reading and stays as it
    is; an aware one (a generation time) is converted.
    """
    local = to_local(value) if value.tzinfo is not None else value
    hour = local.strftime("%I").lstrip("0")
    return f"{hour}:{local:%M} {local:%p}".lower() + f" on {local:%d/%m/%Y}"


def _param(fact_table: FactTable, name: str) -> str:
    return str(fact_table.params.get(name) or "").strip()


def _ministerial_as_at(fact_table: FactTable) -> datetime:
    raw = _param(fact_table, "as_at")
    return datetime.fromisoformat(raw) if raw else fact_table.generated_at


def _incident_line(fact) -> str:
    counts = sorted(fact.breakdown.items(), key=lambda item: (-item[1], item[0]))
    parts = [f"{_humanize(str(name))} {_format_number(count)}" for name, count in counts]
    return "Incidents reported: " + ", ".join(parts)


def render_ministerial(
    template: Template,
    fact_table: FactTable,
    *,
    include_citations: bool = True,
) -> str:
    hazard = _param(fact_table, "hazard").upper()
    title = f"{hazard} SITUATION REPORT" if hazard else "SITUATION REPORT"
    parts = [
        f"# {title}",
        "",
        f"**As at:** {format_as_at(_ministerial_as_at(fact_table))}",
        "",
        f"**Location:** {MINISTRY_LOCATION}",
        "",
    ]
    for label, name in (("Present Activity", "present_activity"), ("Alert Level", "alert_level")):
        value = _param(fact_table, name)
        if value:
            parts.extend([f"**{label}:** {value}", ""])

    overview = _param(fact_table, "situation_overview")
    if overview:
        parts.extend(["## Situation Overview", "", overview, ""])

    facts = [fact for fact in fact_table.facts if fact.metric == "corporation_status"]
    for corporation, label in CORPORATION_LABELS.items():
        parts.extend([f"## {label}", ""])
        own = [fact for fact in facts if fact.scope.get("corporation") == corporation]
        logs = [fact for fact in own if fact.scope.get("kind") == "log"]
        incidents = [fact for fact in own if fact.scope.get("kind") == "incidents"]
        for fact in logs + incidents:
            text = _incident_line(fact) if fact in incidents else str(fact.value)
            marker = f" [{fact.citation.cid}]" if include_citations else ""
            parts.append(f"- {text}{marker}")
        if not own:
            parts.append("- No reports at this time.")
        parts.append("")

    response = _param(fact_table, "ministry_response")
    if response:
        parts.extend([f"## Response from the {MINISTRY_NAME}", "", response, ""])

    parts.append("END OF REPORT")
    return "\n".join(parts) + "\n"


def render_report(
    template: Template,
    fact_table: FactTable,
    narrative: str,
    *,
    include_citations: bool = True,
) -> str:
    if template.render.layout == "filing":
        return render_filing(
            template, fact_table, narrative, include_citations=include_citations
        )
    if template.render.layout == "ministerial":
        return render_ministerial(template, fact_table, include_citations=include_citations)

    title = _document_title(template, fact_table)
    prose = narrative.strip()
    if not include_citations:
        prose = _strip_citations(prose)

    parts = [f"# {title}", ""]
    if prose:
        parts.extend([prose, ""])

    table_blocks = []
    for fact in fact_table.facts:
        if not fact.breakdown:
            continue
        heading = _humanize(fact.metric)
        if include_citations:
            heading = f"{heading} ({fact.citation.cid})"
        table_blocks.append(f"**{heading}**")
        table_blocks.append("")
        table_blocks.append("| Key | Value |")
        table_blocks.append("|---|---|")
        for key, value in fact.breakdown.items():
            table_blocks.append(f"| {_label(str(key))} | {value} |")
        table_blocks.append("")

    if table_blocks:
        parts.append("## Data Tables")
        parts.extend(table_blocks)

    if fact_table.gaps:
        parts.append("## Data Gaps")
        for gap in fact_table.gaps:
            parts.append(f"- {gap}")
        parts.append("")

    if include_citations and template.render.include_citation_appendix:
        parts.append("## Citation Appendix")
        for fact in fact_table.facts:
            citation = fact.citation
            parts.append(_citation_appendix_line(citation))

    return "\n".join(parts)
