from app.modules.capture.schemas import CaptureWorkingSet, MissingField


def missing_fields(working: CaptureWorkingSet) -> list[MissingField]:
    missing: list[MissingField] = []
    manual = set(working.manual_fields)
    # "none" is both the default and a legal answer. Provenance is what tells
    # the two apart: an officer who chose it has a manual_fields entry.
    if working.alert_level == "none" and "alert_level" not in manual:
        missing.append(
            MissingField(path="alert_level", message="Current alert level for the region")
        )
    if working.as_at is None:
        missing.append(
            MissingField(path="as_at", message="Time this report is accurate as at")
        )
    for index, incident in enumerate(working.incidents):
        prefix = f"incidents[{index}]"
        if not incident.event_date:
            missing.append(
                MissingField(path=f"{prefix}.event_date", message="Date of the incident")
            )
        if not incident.incident_type:
            missing.append(
                MissingField(path=f"{prefix}.incident_type", message="Incident type")
            )
        casualties_unknown = (
            incident.injuries_count is None
            and incident.injuries_occurred is None
            and incident.deaths_count is None
            and incident.deaths_occurred is None
        )
        if casualties_unknown:
            missing.append(
                MissingField(
                    path=f"{prefix}.casualties",
                    message="Whether injuries or deaths occurred",
                )
            )
    return missing
