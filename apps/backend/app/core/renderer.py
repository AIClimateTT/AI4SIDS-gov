import re

from app.core.contracts import FactTable, Template
from app.modules.survey123.normalize import CORPORATION_LABELS

# Matches the [C001] markers the composer is told to emit, plus any space
# ahead of them, so stripping "injured [C005]." leaves "injured." not
# "injured ." — the final variant is prose a reader sees, not a QC view.
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
    corp = fact_table.params.get("corporation")
    if not corp:
        return template.title
    name = _label(str(corp))
    if template.render.layout == "filing":
        return f"{name} Situation Report"
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
    """Render the filing layout.

    With ``include_citations`` the output is the draft an officer checks its
    figures against. Without it, the same facts render as the document that
    gets issued: no [Cxxx] markers, no Cite columns, no appendix.
    """
    parts = [f"# {_document_title(template, fact_table)}", ""]

    def cited(cells: list[str], cid: str) -> list[str]:
        return cells + [f"[{cid}]"] if include_citations else cells

    def headers(names: list[str]) -> list[str]:
        return names + ["Cite"] if include_citations else names

    # Words first, tables after — the issued document is read as prose, with
    # the register underneath as the figures that prose is about.
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
            parts.append(_citation_appendix_line(citation))

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
