from app.modules.capture.schemas import MissingField
from app.modules.whatsapp.extract import WhatsAppWorkingSet
from app.modules.whatsapp.provenance import incident_path, log_path


def missing_fields(working: WhatsAppWorkingSet) -> list[MissingField]:
    missing: list[MissingField] = []
    if working.as_at is None:
        missing.append(
            MissingField(path="as_at", message="Time this report is accurate as at")
        )
    for incident in working.incidents:
        if incident.corporation is None:
            missing.append(
                MissingField(
                    path=incident_path(incident.row_id, "corporation"),
                    message="Assign a corporation",
                )
            )
        if incident.included and not incident.incident_summary.strip():
            missing.append(
                MissingField(
                    path=incident_path(incident.row_id, "incident_summary"),
                    message="Summary for this incident",
                )
            )
    for log in working.logs:
        if log.corporation is None:
            missing.append(
                MissingField(
                    path=log_path(log.row_id, "corporation"),
                    message="Assign a corporation",
                )
            )
        if log.included and not log.statement.strip():
            missing.append(
                MissingField(
                    path=log_path(log.row_id, "statement"),
                    message="Statement for this log",
                )
            )
    return missing
