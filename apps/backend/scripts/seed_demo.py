"""Load a realistic demo dataset.

Writes CSVs to fixtures/demo/ and ingests them, so the files stay inspectable
and editable afterwards rather than the data existing only inside the database.

Shapes the data on the three real documents in docs/examples/: a June 2023
adverse-weather event, five corporations filing SITREPs with different alert
levels and volumes, and one (Siparia) filing nothing — the "no reports at this
time" case the Full Sitrep 2023 document actually contains.

Survey123 rows are generated for the SAME window so the ministerial report has
something to corroborate against. They deliberately DIVERGE from the SITREP
counts: field observation and a corporation's signed-off figures are different
things, and a report that shows them agreeing perfectly would hide the whole
point of keeping the two sources separate.

Usage (destructive — truncates every data table first):
    cd apps/backend && .venv/bin/python scripts/seed_demo.py
"""

import csv
import random
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete  # noqa: E402

from app.config import settings  # noqa: E402
from app.core.template_store import import_template_directory  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.modules.sitreps.ingest import ingest_submission  # noqa: E402
from app.modules.sitreps.models import (  # noqa: E402
    Event,
    SitrepIncident,
    SituationLog,
    Submission,
)
from app.modules.survey123.ingest import ingest_csv  # noqa: E402
from app.modules.survey123.models import FieldObservation  # noqa: E402

BACKEND = Path(__file__).resolve().parent.parent
DEMO = BACKEND / "fixtures" / "demo"
TEMPLATES = BACKEND / "app" / "templates" / "definitions"

random.seed(20230627)  # reproducible

# corporation -> (alert level, incident rows, log rows, situation overview)
CORPS = {
    "diego_martin_regional_corporati": (
        "discontinued",
        15,
        "The Adverse Weather Alert Yellow Level #2 issued by the Trinidad and Tobago "
        "Meteorological Service produced heavy rainfall and high winds which affected "
        "the Borough of Diego Martin. This rainfall caused roofing damages, fallen "
        "trees, landslides and flooding across the Diego Martin Region.",
    ),
    "tunapuna_piarco_regional_corpor": (
        "yellow",
        12,
        "On 16th June the MET Office issued a Localized Flood Alert - Yellow Level. "
        "Two further Yellow Alerts have since been issued and remain in effect. "
        "Landslides and flash flooding have been reported across the region.",
    ),
    "san_juan_laventille_regional_co": (
        "yellow",
        18,
        "Sustained rainfall across the region produced widespread flooding in low-lying "
        "communities and several landslides along hillside access roads. The Emergency "
        "Operations Centre was activated.",
    ),
    "sangre_grande_regional_corporat": ("green", 6, "Scattered showers with localised ponding. Monitoring continues."),
    "penal_debe_regional_corporation": ("green", 4, "Isolated flooding in low-lying agricultural areas. No shelters opened."),
    # Siparia files nothing at all — the Full Sitrep's "No reports at this time".
}

STREETS = {
    "diego_martin_regional_corporati": [
        ("Petit Valley", "Cameron Road"), ("Maraval", "Saddle Road"),
        ("Diamond Vale", "Opal Gardens"), ("River Estate", "Yellow Bird Drive"),
        ("Paramin", "Saut Deau Road"), ("Morne Coco", "Cassia Drive"),
        ("Four Roads", "Upper San Diego Park"), ("Haleland Park", "Grapefruit Crescent"),
        ("Bagatelle", "Mahogany Trace"), ("Carenage", "Bay Road"),
    ],
    "tunapuna_piarco_regional_corpor": [
        ("St Joseph", "Victoria Street"), ("Tunapuna", "2nd Trace Maingot Road"),
        ("Caura", "Caura Road"), ("Warrenville", "Marshall Trace"),
        ("Warrenville", "Ajodha Street"), ("Tunapuna", "Pentecostal Road"),
        ("Wallerfield", "Jacob Hill"), ("St Augustine", "Freeman Road"),
        ("D'abadie", "Boys Lane Extension"), ("Wallerfield", "Mexico Road"),
    ],
    "san_juan_laventille_regional_co": [
        ("San Juan", "Aranguez Main Road"), ("Barataria", "Sixth Avenue"),
        ("Laventille", "Picton Road"), ("Morvant", "Never Dirty Road"),
        ("San Juan", "El Socorro Road"), ("Success", "Success Village Road"),
        ("Beetham", "Beetham Gardens"), ("Laventille", "Upper St Barbs Road"),
        ("Barataria", "Ninth Street"), ("Petit Bourg", "Saddle Road"),
    ],
    "sangre_grande_regional_corporat": [
        ("Sangre Grande", "Ojoe Road"), ("Cumuto", "Cumuto Main Road"),
        ("Manzanilla", "Manzanilla Beach Road"), ("Vega de Oropouche", "Toco Main Road"),
    ],
    "penal_debe_regional_corporation": [
        ("Penal", "Clarke Road"), ("Debe", "SS Erin Road"),
        ("Barrackpore", "Papourie Road"), ("Penal", "Rochard Douglas Road"),
    ],
}

TYPES = ["flooding_", "landslide", "fallen_tree", "blown_off_roof"]
ACTIONS = [
    "DMU team responded and cleared the roadway.",
    "Assessment complete. Tarpaulin issued to resident.",
    "Referred to Self-Help for further assistance.",
    "Cleaning hamper issued. Referred to Social Development.",
    "Assessment complete. Referred to Ministry of Works.",
]

INCIDENT_HEADER = [
    "Row ID", "Community", "Street", "Incident Type", "Date of Event", "Incident Summary",
    "Name of Person", "Contact Information", "Injuries Occurred", "Injuries Count",
    "Deaths Occurred", "Deaths Count", "Building Damage", "Special Needs Occupants",
    "Estimated Damage Cost", "Action Taken", "Relief Supplied", "Forwarded To Agency",
    "Further Assessment Required", "Other Follow Up",
]

LOG_HEADER = ["Category", "Statement", "Item", "Quantity", "Unit", "Status"]


def incident_rows(corp: str, count: int) -> list[list]:
    """Incident rows. PII columns are populated on purpose — the ingest drops them,
    and a demo that never exercises that is not demonstrating anything."""
    places = STREETS[corp]
    rows = []
    for i in range(1, count + 1):
        community, street = places[(i - 1) % len(places)]
        kind = TYPES[(i - 1) % len(TYPES)]
        injured = i % 7 == 0
        day = 27 + (i % 4)
        rows.append([
            str(i), community, street, kind, f"2023-06-{day:02d}",
            f"{kind.replace('_', ' ').strip().title()} reported at {street}.",
            f"Resident {i}", f"868555{1000 + i}",
            "Yes" if injured else "No", "1" if injured else "",
            "No", "",
            "Roof and ceiling water damage" if kind == "blown_off_roof" else "Ground floor inundated",
            "1" if i % 5 == 0 else "",
            f"${random.choice([1500, 2800, 4500, 9000, 12500, 22000]):,}" if i % 3 else "",
            ACTIONS[(i - 1) % len(ACTIONS)],
            "Yes" if i % 2 else "No", "Yes" if i % 3 else "No",
            "Yes" if i % 4 == 0 else "No", "No",
        ])
    return rows


def log_rows(corp: str) -> list[list]:
    base = [
        ["relief_distributed", "Tarpaulins issued to affected residents", "tarpaulins", str(6 + len(corp) % 14), "units", "completed"],
        ["relief_distributed", "Sandbags distributed to vulnerable properties", "sandbags", str(30 + len(corp) % 200), "bags", "completed"],
        ["relief_distributed", "Cleaning hampers issued to flood-affected households", "cleaning hampers", "3", "units", "completed"],
        ["resource", "Additional tarpaulins held in reserve at the corporation store", "tarpaulins", "25", "units", "in_stock"],
        ["facility", "Designated emergency shelters inspected and confirmed ready", "shelters", str(8 + len(corp) % 15), "facilities", "inspected"],
        ["personnel", "Informed Chairman of Council and CEO of the adverse weather alert", "", "", "", "completed"],
        ["personnel", "CERT members and shelter managers placed on alert and standby", "", "", "", "on_standby"],
        ["activity", "Tree cutting team deployed to clear obstructed roadways", "", "", "", "ongoing"],
        ["activity", "Re-check of relief items completed at the corporation store", "", "", "", "completed"],
    ]
    return base


def survey123_rows(header: list[str], count: int) -> list[list]:
    """Field observations for the same window. Deliberately a different count and
    mix from the SITREPs — corroboration, not a copy."""
    idx = {name: i for i, name in enumerate(header)}
    corps = list(CORPS) + ["siparia_regional_corporation"]
    rows = []
    for i in range(1, count + 1):
        corp = corps[i % len(corps)]
        community, street = STREETS.get(corp, [("Siparia", "High Street")])[i % len(STREETS.get(corp, [1]))]
        row = [""] * len(header)
        row[idx["ObjectID"]] = str(1000 + i)
        row[idx["GlobalID"]] = f"FIELD-{i:04d}"
        row[idx["CreationDate"]] = "2023-06-28T09:00:00"
        row[idx["EditDate"]] = "2023-06-28T09:00:00"
        row[idx["Name of Officer"]] = f"Field Officer {i}"
        row[idx["Position"]] = "DMU Field Officer"
        row[idx["Date of Event"]] = f"2023-06-{27 + (i % 4):02d}T00:00:00"
        row[idx["Name of Person"]] = f"Occupant {i}"
        row[idx["Contact Information"]] = f"868666{2000 + i}"
        row[idx["Address"]] = f"{i} {street}, {community}"
        row[idx["Community"]] = community
        row[idx["Municipal Boundary"]] = corp
        row[idx["Incident Type"]] = TYPES[i % len(TYPES)].replace("flooding_", "Flooding_")
        row[idx["Incident Summary"]] = f"Field assessment at {street}."
        row[idx["Did any injuries occur?"]] = "False"
        row[idx["Did any deaths occur?"]] = "False"
        row[idx["Building Damage"]] = "Water damage observed"
        row[idx["Estimate Cost of Damage"]] = str(random.choice([1200, 3400, 7800, 15000]))
        # A fifth are still pending validation, so data_coverage has something
        # real to report and the minister sees a genuine coverage caveat. The
        # real export leaves the cell EMPTY for pending — a literal
        # "NotValidated" is an unrecognised value and only warns.
        row[idx["Validated/NotValidated"]] = "" if i % 5 == 0 else "Validated"
        row[idx["Identification Card Number"]] = f"ID{i:06d}"
        rows.append(row)
    return rows


def write_csv(path: Path, header: list[str], rows: list[list]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    return path


def main() -> None:
    print(f"target: {settings.database_url}")
    session = SessionLocal()

    for model in (SitrepIncident, SituationLog, Submission, Event, FieldObservation):
        session.execute(delete(model))
    session.commit()
    print("cleared existing data")

    import_template_directory(TEMPLATES, session)
    print("imported templates")

    survey_header = next(csv.reader(open(BACKEND / "fixtures" / "sample_small.csv", encoding="utf-8")))
    survey_path = write_csv(
        DEMO / "survey123_june_2023.csv", survey_header, survey123_rows(survey_header, 42)
    )
    result = ingest_csv(survey_path, session, settings.dedup_salt)
    print(f"survey123: {result.rows_inserted} field observations")

    for corp, (alert, count, overview) in CORPS.items():
        event = Event(
            corporation=corp, title="Adverse Weather June 2023", hazard_type="wind",
            started_at=datetime(2023, 6, 27), created_at=datetime(2023, 6, 27),
        )
        session.add(event)
        session.commit()

        inc = write_csv(DEMO / f"{corp}_incidents.csv", INCIDENT_HEADER, incident_rows(corp, count))
        logs = write_csv(DEMO / f"{corp}_logs.csv", LOG_HEADER, log_rows(corp))

        # Two filings per event so "Situation Report #2" is real, and the second
        # re-sends the cumulative table to exercise supersession.
        ingest_submission(
            session, corporation=corp, as_at=datetime(2023, 6, 28, 9, 0),
            event_id=event.id, alert_level="yellow", present_activity="Adverse Weather Alert",
            situation_overview=overview, incidents_path=inc,
        )
        r = ingest_submission(
            session, corporation=corp, as_at=datetime(2023, 6, 30, 16, 0),
            event_id=event.id, alert_level=alert, present_activity="Adverse Weather Alert",
            situation_overview=overview, incidents_path=inc, logs_path=logs,
        )
        print(
            f"{corp}: report #{r.sequence_no}, {r.incidents_updated} incidents, "
            f"{r.logs_inserted} logs, alert={alert}, {len(r.row_errors)} row errors"
        )

    session.close()
    print("\nSiparia filed nothing — the ministerial report should say so.")


if __name__ == "__main__":
    main()
