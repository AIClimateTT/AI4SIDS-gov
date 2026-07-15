from app.core.contracts import FactTable, Template


def render_report(template: Template, fact_table: FactTable, narrative: str) -> str:
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
