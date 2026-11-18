from app.modules.capture.schemas import CaptureWorkingSet, MissingField, reads_like_alert


def missing_fields(working: CaptureWorkingSet) -> list[MissingField]:
    missing: list[MissingField] = []
    manual = set(working.manual_fields)
    # "none" is both the default and a legal answer. Provenance is what tells
    # the two apart: an officer who chose it has a manual_fields entry.
    if working.alert_level == "none" and "alert_level" not in manual:
        missing.append(
            MissingField(path="alert_level", message="Current alert level for the region")
        )
    if working.alert_detail and not reads_like_alert(working.alert_detail):
        # Couva typed "No relief distributed" here and it went out as the
        # filing's Alert Level.
        missing.append(
            MissingField(
                path="alert_detail",
                message="Alert wording does not read like a Met Office alert; check it is in the right box",
            )
        )
    if working.as_at is None:
        missing.append(
            MissingField(path="as_at", message="Time this report is accurate as at")
        )
    for index, incident in enumerate(working.incidents):
        prefix = f"incidents[{index}]"
        if incident.is_blank():
            # An empty "+ Add manually" row is not filed; nothing to chase yet.
            continue
        if not incident.community and not incident.street:
            missing.append(
                MissingField(
                    path=f"{prefix}.community",
                    message="Where it happened (community or street)",
                )
            )
        if incident.incident_scope == "household" and not incident.house_number:
            missing.append(
                MissingField(path=f"{prefix}.house_number", message="House number or LP")
            )
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
