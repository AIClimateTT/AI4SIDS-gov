from app.modules.capture.schemas import CaptureIncident, CaptureLog, CaptureWorkingSet


def _cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def incident_to_csv_row(incident: CaptureIncident) -> dict[str, str]:
    return {
        "Row ID": incident.row_id,
        "Community": _cell(incident.community),
        "Street": _cell(incident.street),
        "Incident Type": _cell(incident.incident_type or incident.raw_incident_type),
        "Date of Event": _cell(incident.event_date),
        "Incident Summary": _cell(incident.incident_summary),
        "Injuries Occurred": _cell(incident.injuries_occurred),
        "Injuries Count": _cell(incident.injuries_count),
        "Deaths Occurred": _cell(incident.deaths_occurred),
        "Deaths Count": _cell(incident.deaths_count),
        "Building Damage": _cell(incident.building_damage),
        "Special Needs Occupants": _cell(incident.special_needs_occupants),
        "Estimated Damage Cost": _cell(incident.estimated_damage_cost),
        "Action Taken": _cell(incident.action_taken),
        "Relief Supplied": _cell(incident.relief_supplied),
        "Forwarded To Agency": _cell(incident.forwarded_to_agency),
        "Further Assessment Required": _cell(incident.further_assessment_required),
        "Other Follow Up": _cell(incident.other_follow_up),
    }


def log_to_csv_row(log: CaptureLog) -> dict[str, str]:
    return {
        "Category": log.category,
        "Statement": log.statement,
        "Item": _cell(log.item),
        "Quantity": _cell(log.quantity),
        "Unit": _cell(log.unit),
        "Status": _cell(log.status),
    }


def working_set_to_ingest_rows(
    working: CaptureWorkingSet,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    return (
        [incident_to_csv_row(item) for item in working.incidents],
        [log_to_csv_row(item) for item in working.logs],
    )
