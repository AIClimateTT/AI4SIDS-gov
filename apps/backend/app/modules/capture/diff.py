"""What one change did to a capture working set, as readable lines."""

_TOP_FIELDS = (
    "as_at",
    "alert_level",
    "alert_detail",
    "present_activity",
    "situation_overview",
    "manual_fields",
)


def _row_changes(kind: str, before: list[dict], after: list[dict]) -> list[str]:
    old = {row.get("row_id"): row for row in before}
    new = {row.get("row_id"): row for row in after}
    out: list[str] = []
    for row_id, row in new.items():
        if row_id not in old:
            label = (
                row.get("incident_summary")
                or row.get("statement")
                or " · ".join(
                    str(row[key])
                    for key in ("incident_type", "community", "street")
                    if row.get(key)
                )
            )
            out.append(f"added {kind} {row_id}: {label}")
            continue
        for key, value in row.items():
            if old[row_id].get(key) != value:
                out.append(
                    f"{kind} {row_id}.{key}: {old[row_id].get(key)!r} → {value!r}"
                )
    out += [f"removed {kind} {row_id}" for row_id in old if row_id not in new]
    return out


def working_changes(before: dict | None, after: dict) -> list[str]:
    """What one change did to the working set, as readable lines."""
    before = before or {}
    out = [
        f"{key}: {before.get(key)!r} → {after.get(key)!r}"
        for key in _TOP_FIELDS
        if before.get(key) != after.get(key) and before
    ]
    out += _row_changes("incident", before.get("incidents") or [], after.get("incidents") or [])
    out += _row_changes("log", before.get("logs") or [], after.get("logs") or [])
    return out
