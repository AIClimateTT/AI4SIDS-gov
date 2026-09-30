# Outstanding issues

Known problems deferred to a later iteration. Each entry says what is wrong,
how it was found, and what a fix would need to decide.

## Survey123 source-data quality

Found on 2026-09-28 while ingesting a full ArcGIS export (`survey_0.csv`,
15,221 rows, 2021–2026) after the ingestion hardening on
`feat/improve-ingestion`. None of these block an upload; they reduce the
accuracy of what is stored.

### 1. Implausible event dates

"Date of Event" holds values well outside the survey's life, e.g.
`11/27/1902`, `6/19/1987`, `9/10/2008`. The earliest stored event date is
1902-11-27. These are data-entry errors in ArcGIS, not parse errors.

- Effect: rows fall outside any realistic date filter, or skew "earliest"
  figures.
- Decide: reject, flag (like `is_duplicate`), or report as a warning on
  upload. A plausible window (e.g. not before the survey launched, not after
  the creation date) is the likely rule.

### 2. Free-text overflow occupant counts

When "Household Occupants" is `other`, the count comes from "If more than 6
persons - Household Occupants", which officers type freely: `4 adults 9
children`, `Seven(7)`, `9 people`, `11 kids and 7 adults`, names of
occupants, or `Yes`. `parse_occupants` only reads a bare number or
`N persons`, so these rows store `occupants_count = NULL` and log
`could not parse overflow occupants value`.

- Effect: large households, the ones that matter most for relief, are
  undercounted in occupant metrics.
- Decide: sum "N adults M children" patterns and number words, or surface
  the rows for manual correction. Names typed into this field are PII and
  must not be stored.

### 3. Unmapped follow-up token `Relocate_to_Shelter`

"Follow Up Recommendation" contains `Relocate_to_Shelter`, which
`parse_follow_up_flags` does not recognise. Every occurrence logs
`unmapped Follow Up Recommendation token` and the recommendation is lost
from `follow_up_flags`.

- Effect: shelter relocations are not counted; logs are noisy.
- Decide: add a `relocated_to_shelter` flag and include it in the relief
  metrics.

## Repository hygiene

### 4. Real survey export is not git-ignored

`apps/backend/survey_0.csv` is real data containing names, phone numbers
and national ID numbers. It is untracked but not in `.gitignore`, so a
`git add .` would commit it. Move it out of the repository or add an ignore
rule for raw exports.

## Pre-existing test failure

### 5. `test_the_split_migration_preserves_every_row`

`tests/test_migrations.py::test_the_split_migration_preserves_every_row`
fails with `sqlite3.OperationalError: no such table: incidents`. It failed
on a clean branch before the ingestion work and is unrelated to it.
