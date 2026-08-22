from app.core.contracts import FactTable, Template


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
    if not rows:
        return []
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")
    return lines


def render_filing(template: Template, fact_table: FactTable, narrative: str) -> str:
    parts = [f"# {template.title}", ""]

    count = next((fact for fact in fact_table.facts if fact.metric == "incident_count"), None)
    if count is not None and count.value and count.breakdown:
        rows = [
            [key, _format_number(value), f"[{count.citation.cid}]"]
            for key, value in count.breakdown.items()
            if value
        ]
        if rows:
            parts.extend(["## Situation summary", ""])
            parts.extend(_md_table(["Type", "Count", "Cite"], rows))

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
                [
                    fact.scope.get("item") or fact.scope.get("statement") or "",
                    _format_number(fact.value),
                    fact.unit or "",
                    fact.scope.get("status") or "",
                    f"[{fact.citation.cid}]",
                ]
            )
        parts.extend(_md_table(["Item", "Quantity", "Unit", "Status", "Cite"], rows))

    register = [fact for fact in fact_table.facts if fact.metric == "incident_register"]
    if register:
        parts.extend(["## Incidents", ""])
        rows = []
        for fact in register:
            rows.append(
                [
                    fact.scope.get("date") or "",
                    _place(fact.scope),
                    fact.scope.get("type") or "",
                    fact.scope.get("summary") or "",
                    fact.scope.get("injuries") or "",
                    fact.scope.get("deaths") or "",
                    fact.scope.get("action") or "",
                    f"[{fact.citation.cid}]",
                ]
            )
        parts.extend(
            _md_table(
                ["Date", "Place", "Type", "Summary", "Injuries", "Deaths", "Action", "Cite"],
                rows,
            )
        )

    activities = [fact for fact in fact_table.facts if fact.metric == "activity_log"]
    if activities:
        parts.extend(["## Activities", ""])
        for fact in activities:
            parts.append(f"- {fact.value} [{fact.citation.cid}]")
        parts.append("")

    if narrative.strip():
        parts.extend([narrative.strip(), ""])

    gaps = [
        gap
        for gap in fact_table.gaps
        if gap.strip() and gap.strip().lower() != "none"
    ]
    if gaps:
        parts.append("## Data Gaps")
        for gap in gaps:
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


def render_report(template: Template, fact_table: FactTable, narrative: str) -> str:
    if template.render.layout == "filing":
        return render_filing(template, fact_table, narrative)

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
