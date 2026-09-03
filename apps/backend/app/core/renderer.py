import re

from app.core.contracts import FactTable, Template

# Matches the [C001] markers the composer is told to emit, plus any space
# ahead of them, so stripping "injured [C005]." leaves "injured." not
# "injured ." — the final variant is prose a reader sees, not a QC view.
_CITATION_MARKER = re.compile(r"[ \t]*\[C\d{3}\]")


def _strip_citations(text: str) -> str:
    return _CITATION_MARKER.sub("", text)


def _humanize(slug: str) -> str:
    """Turn an incident type slug into label case.

    Officers' type values arrive as slugs ("blown_off_roof") and some carry a
    stray trailing underscore from data entry, which must not reach a filing.
    """
    words = slug.strip().strip("_").replace("_", " ").strip()
    if not words:
        return slug
    return words[0].upper() + words[1:]


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
    """Render the filing layout.

    With ``include_citations`` the output is the draft an officer checks its
    figures against. Without it, the same facts render as the document that
    gets issued: no [Cxxx] markers, no Cite columns, no appendix.
    """
    parts = [f"# {template.title}", ""]

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
            cited([_humanize(key), _format_number(value)], count.citation.cid)
            for key, value in count.breakdown.items()
            if value
        ]
        if rows:
            parts.extend(["## Situation summary", ""])
            parts.extend(_md_table(headers(["Type", "Count"]), rows))

    relief = [
        fact
        for fact in fact_table.facts
        if fact.metric == "relief_stock_summary" and fact.value
    ]
    if relief:
        parts.extend(["## Relief and resources", ""])
        rows = []
        for fact in relief:
            rows.append(
                cited(
                    [
                        fact.scope.get("item") or fact.scope.get("statement") or "",
                        _format_number(fact.value),
                        fact.unit or "",
                        _humanize(fact.scope.get("status") or ""),
                    ],
                    fact.citation.cid,
                )
            )
        parts.extend(_md_table(headers(["Item", "Quantity", "Unit", "Status"]), rows))

    register = [fact for fact in fact_table.facts if fact.metric == "incident_register"]
    if register:
        parts.extend(["## Incidents", ""])
        rows = []
        for fact in register:
            rows.append(
                cited(
                    [
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
                    ["Date", "Place", "Type", "Summary", "Injuries", "Deaths", "Action"]
                ),
                rows,
            )
        )

    activities = [fact for fact in fact_table.facts if fact.metric == "activity_log"]
    if activities:
        parts.extend(["## Activities", ""])
        for fact in activities:
            marker = f" [{fact.citation.cid}]" if include_citations else ""
            parts.append(f"- {fact.value}{marker}")
        parts.append("")

    gaps = [
        gap
        for gap in fact_table.gaps
        if gap.strip() and gap.strip().lower() != "none"
    ]
    if gaps:
        # A reader of the issued filing still needs to know what was not
        # recorded — only the internal QC framing is dropped.
        parts.append("## Data Gaps" if include_citations else "## Information not yet available")
        for gap in gaps:
            parts.append(f"- {gap}")
        parts.append("")

    if include_citations and template.render.include_citation_appendix:
        parts.append("## Citation Appendix")
        for fact in fact_table.facts:
            citation = fact.citation
            parts.append(
                f"- [{citation.cid}] {citation.description} "
                f"(query_ref: `{citation.query_ref}`, as_of: {citation.as_of})"
            )

    return "\n".join(parts)


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

    parts = [f"# {template.title}", "", narrative.strip(), ""]

    table_blocks = []
    for fact in fact_table.facts:
        if not fact.breakdown:
            continue
        table_blocks.append(f"**{fact.metric}** ({fact.citation.cid})")
        table_blocks.append("")
        table_blocks.append("| Key | Value |")
        table_blocks.append("|---|---|")
        for key, value in fact.breakdown.items():
            table_blocks.append(f"| {key} | {value} |")
        table_blocks.append("")

    if table_blocks:
        parts.append("## Data Tables")
        parts.extend(table_blocks)

    if fact_table.gaps:
        parts.append("## Data Gaps")
        for gap in fact_table.gaps:
            parts.append(f"- {gap}")
        parts.append("")

    if template.render.include_citation_appendix:
        parts.append("## Citation Appendix")
        for fact in fact_table.facts:
            citation = fact.citation
            parts.append(
                f"- [{citation.cid}] {citation.description} "
                f"(query_ref: `{citation.query_ref}`, as_of: {citation.as_of})"
            )

    return "\n".join(parts)
