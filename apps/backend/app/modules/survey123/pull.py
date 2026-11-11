from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.contracts import IngestResult
from app.modules.survey123.client import fetch_layer
from app.modules.survey123.ingest import (
    VALIDATION_COLUMN,
    IngestFormatError,
    ingest_rows,
    normalize_headers,
    require_survey123_headers,
)

# A published survey labels each field with its question text, which is the
# column name an export uses. The test survey's layer was loaded from a
# shapefile instead: names cut to ten characters, labels the same as the names.
# Those fields are named here, matched to an export by position and checked
# against it row by row. Fields the parser does not read are left out.
SHORT_FIELD_COLUMNS = {
    "objectid": "ObjectID",
    # The original GlobalID, kept as text. The layer's own GlobalID is new.
    "globalid": "GlobalID",
    "creationda": "CreationDate",
    "editdate": "EditDate",
    "date_of_ev": "Date of Event",
    "time_of_ev": "Time of Event",
    "name_of_pe": "Name of Person",
    "address": "Address",
    "community_": "Community",
    "administra": "Municipal Boundary",
    "hazard_typ": "Incident Type",
    "hazard_t_1": "Other - Incident Type",
    "incident_s": "Incident Summary",
    "household_": "Household Occupants",
    "household1": "If more than 6 persons - Household Occupants",
    "did_injuri": "Did any injuries occur?",
    "injuries_": "Injuries",
    "did_any_de": "Did any deaths occur?",
    "deaths": "Deaths",
    "building_d": "Building Damage",
    "crops_and_": "Crops and Livestock",
    "personal_i": "Personal Items",
    "appliances": "Furniture and Appliances",
    "action_tak": "Action Taken",
    "relief_ite": "Relief Items",
    "shelter": "Shelter",
    "please_ind": "Please indicate the number of special needs occupants",
    "estimate_c": "Estimate Cost of Damage",
    "identifi_2": "Identification Card Number",
    "field_43": "Follow Up Recommendation",
    "assessment": "Assessment Date",
    "validatedn": "Validated/NotValidated",
    "flood_type": "Flood Type",
    "flood_trig": "Flood Trigger",
    "flood_heig": "Flood Height",
    "community": "Community_2",
}

# Date-only questions. Survey123 stores them at noon on the device, so the
# parser reads the Trinidad day from the timestamp. A value at exactly midnight
# UTC was stored as a bare date, and its UTC day is the answer.
CALENDAR_COLUMNS = frozenset({"Date of Event", "Assessment Date"})

# Shapefiles and spreadsheets write 1899-12-30 for a blank date.
EARLIEST_DATE = datetime(1900, 1, 1, tzinfo=timezone.utc)

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def layer_header(fields: list[dict]) -> list[str]:
    """Column names for the layer's fields, as an export would write them."""
    columns = []
    for field in fields:
        name = field["name"]
        alias = (field.get("alias") or name).strip()
        unlabelled = alias.lower() == name.lower()
        columns.append(SHORT_FIELD_COLUMNS.get(name.lower(), alias) if unlabelled else alias)
    return normalize_headers(columns) + ["x", "y"]


def _date_cell(value: int | float, column: str) -> str:
    moment = EPOCH + timedelta(milliseconds=value)
    if moment < EARLIEST_DATE:
        return ""
    if column in CALENDAR_COLUMNS and moment.time() == datetime.min.time():
        return moment.date().isoformat()
    return moment.isoformat()


def _cell(value, field_type: str, column: str) -> str:
    if value is None:
        return ""
    # Newer date types arrive as ISO strings already; the classic one as epoch ms.
    if field_type == "esriFieldTypeDate" and isinstance(value, (int, float)):
        return _date_cell(value, column)
    # Counts come back as doubles, and the parser reads "3" but not "3.0".
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def feature_row(feature: dict, fields: list[dict], header: list[str]) -> dict[str, str]:
    attributes = feature.get("attributes", {})
    row = {
        column: _cell(attributes.get(field["name"]), field.get("type", ""), column)
        for field, column in zip(fields, header)
    }
    geometry = feature.get("geometry") or {}
    row["x"] = _cell(geometry.get("x"), "", "x")
    row["y"] = _cell(geometry.get("y"), "", "y")
    return row


def pull_survey123(session: Session, salt: str, layer: int = 0) -> IngestResult:
    """Store the survey's validated responses. Others wait for a later pull."""
    item_id, fields, features = fetch_layer(layer)
    header = layer_header(fields)
    require_survey123_headers(header)
    if VALIDATION_COLUMN not in header:
        raise IngestFormatError(f"Survey layer has no {VALIDATION_COLUMN} field")

    rows = [feature_row(feature, fields, header) for feature in features]
    validated = [row for row in rows if row[VALIDATION_COLUMN].strip().lower() == "validated"]

    result = ingest_rows(header, validated, session, salt, source=f"survey123:{item_id}/{layer}")
    skipped = len(rows) - len(validated)
    if skipped:
        result.warnings.append(
            f"{skipped} response(s) are not marked Validated yet, so they were not stored."
        )
    return result
