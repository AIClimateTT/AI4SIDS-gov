# Merge-Blocking Defects from the Whole-Branch Review

**Date:** 2026-08-05
**Status:** Approved design, ready for implementation planning
**Source:** final whole-branch review of `sitrep-realignment-plan-1` (31 commits). Four defects put a wrong or untraceable number into a ministerial report. All four were found with the full suite green — 320 backend tests, 19 frontend, `alembic check` clean.

---

## 1. Why these four and not the rest

This system's premise is that every number in a generated report is computed deterministically and traces to a cited source. These four are the ones that violate that premise. Each was independently reproduced before being accepted.

The review also raised eight should-fix and six optional items; they are **out of scope** here and listed in §7 so they are not lost.

---

## 2. F1 — Hand-typed cells are silently coerced

`app/modules/sitreps/parse.py:58-72`, via `parse_bool` / `parse_decimal` in `app/modules/survey123/ingest.py:36-61`.

`parse_bool` returns `True` only for the exact string `"true"`. `parse_decimal` returns `None` for anything `Decimal()` rejects. Corporations author these spreadsheets **by hand** — the module's own docstring says so.

Reproduced, one row, no error raised, `row_errors == []`:

| Cell | Typed | Stored |
|---|---|---|
| Estimated Damage Cost | `$12,500` | `None` |
| Injuries Occurred | `Yes` | `False` |
| Deaths Occurred | `Y` | `False` |
| Relief Supplied | `Yes` | `False` |

The report then states **TTD 0 damage** and **0 relief actions**, cited, marked `verification="validated"`.

**This contradicts a rule the same file states 20 lines further down** (`parse.py:85-87`): *"Any number the report later states must come from the quantity column, so an unparseable quantity is rejected rather than silently nulled."* `parse_log_row` rejects `1,200` loudly; `parse_incident_row` swallows `$12,500` silently.

### Decision

Apply the log parser's rule to the incident parser. A **non-empty** cell that fails to parse becomes a `RowError`; an **empty** cell stays `None`/`False` as today.

Booleans accept a documented set, case-insensitively, and reject anything else:
- true: `true`, `yes`, `y`, `1`
- false: `false`, `no`, `n`, `0`, and empty

Currency accepts a leading `$` and thousands separators (`$12,500` → `12500`), because that is what a person types. Anything still unparseable is a row error naming the cell and the value.

**Deliberately not done:** changing `parse_bool`/`parse_decimal` in `survey123/ingest.py`. Survey123 CSVs are machine-generated exports, not hand-typed, and altering shared helpers would change ingest behaviour for 14,942 rows of existing field data. The new strictness belongs to the corp path only.

---

## 3. F2 — `query_ref` advertises filters that were never applied

`app/modules/survey123/metrics.py:38-40`.

`build_query_ref` serialises **every** key in `DataRequirement.params`. `apply_common_filters` consumes only `corporation`, `community`, `date_from`, `date_to`; `base_query` adds `include_pending`. Everything else is dropped silently — and still printed into the citation appendix a Minister reads.

Reproduced:

```
params:    {"source": "sitreps", "incident_type": "flood", "corporation": "diego_martin..."}
query_ref: estimated_damage_total(corporation=diego_martin..., incident_type=flood, source=sitreps)
value:     12500.5     ← spans ALL incident types
```

**This branch introduced it.** Before the split, `source` was a real filter on `Incident.source`. The branch correctly stopped filtering on it but left it printable, so a template stored before the split now silently widens its result set while its `query_ref` line is byte-identical to before.

### Decision

`build_query_ref` renders only the parameters the query actually consumed. A single module-level tuple names them, and both `apply_common_filters`/`base_query` and `build_query_ref` read from it, so the two cannot drift.

Unrecognised keys are **dropped from `query_ref`, not rejected**. Rejecting would break every stored template carrying a legacy `source` key and turn a reporting defect into an outage. The narrower fix restores the guarantee that matters: the audit string describes the query that ran.

---

## 4. F3 — The date rule erases invented figures

`app/core/citation_check.py:21-26`, the `MONTH \s+ YEAR` alternative.

Reproduced against a fact table containing only `15`:

```
passed=True  violations=0   ←  "...[C001]. In May 2500 households were affected."
passed=True  violations=0   ←  "...[C001]. Sept 1200 people were displaced."
```

A wholly invented, uncited 4-digit figure reaches the report with `status: ok`. Both guards fail at once: `_strip_dates` removes the token before `NUMBER_TOKEN_RE` runs, so the sentence has no tokens, so the `continue` skips the missing-citation check too.

The comment directly above the pattern identifies this exact hazard for two-digit numbers (`"In June 15 homes were affected"`) and guards against it. The same hazard for four-digit numbers was left open. `CITATION_RULES` now also instructs the model to write figures as bare digits — the precise shape that collides.

### Decision

`_YEAR = r"(?:19|20)\d{2}"`.

Two characters of regex. It still strips every real date this system will ever contain and stops erasing `2500`, `1200`, `9999`. The residual hole — a genuine figure between 1900 and 2099 immediately following a month name — is far narrower than the current one and is accepted.

---

## 5. F4 — Event-less incident filing inflates counts and collides citations

`app/modules/sitreps/models.py:120-122` and `app/modules/sitreps/ingest.py:119`.

`record_ref` is `f"{corporation}:{event_id or '-'}:{row_id}"`, so every event-less row renders `event_id` as `-`. Supersession is skipped entirely when `event_id is None`. Reproduced — the same 2-row cumulative table filed as three daily event-less submissions:

```
truth:                    2 incidents
incident_count:           6   {'fire': 3, 'flooding_': 3}
relief_actions_summary:   2   ← contradicts incident_count in the same report
record_ids:               corp:-:1, corp:-:1, corp:-:1, corp:-:2, corp:-:2, corp:-:2
```

Three failures at once: the count is triple the truth; one identifier names three different rows, so no auditor can trace the figure; and two metrics in the same report disagree because `relief_actions_summary` dedupes on that ref while `incident_count` does not.

Filing a cumulative table is the documented corp workflow, and `POST /submissions` leaves `event_id` optional with no warning.

### Decision

**A submission carrying an incidents file must name an event.** `POST /submissions` rejects one that does not, with 400 and a message saying why. Situation logs remain filable without an event — they are point-in-time state, they never supersede, and nothing about them collides.

This makes supersession always apply to incidents, so re-filing a cumulative table can never inflate a count, and it makes `record_ref` unique by construction.

**Additionally**, `record_ref` includes `submission_id` so it names exactly one row even for historic event-less rows already in a database. Belt and braces: the API constraint prevents new collisions, the identifier change makes existing ones traceable.

The CLI gets the same validation. §7 records that the CLI currently bypasses the corporation check too.

---

## 6. Testing

Each fix lands with the reproduction above as a regression test, because each one passed a green suite.

- **F1:** a row with `$12,500`, `Yes`, `Y` produces a `RowError` naming the cell; `$12,500` alone parses to `12500` once the currency handling lands; an empty cell still yields `None`/`False` without error.
- **F2:** `query_ref` for params carrying `source` and `incident_type` names neither; it still names `corporation` and the date window; a metric's value is unchanged by the presence of an ignored key.
- **F3:** the three reproduced sentences each produce a violation; every real date form from the existing tests still produces none.
- **F4:** a submission with an incidents file and no `event_id` returns 400; one with logs only and no event succeeds; the three-times-cumulative filing that produced 6 now cannot be filed; `record_ref` differs across two submissions of the same row.

---

## 7. Out of scope — carried forward, not lost

From the review's should-fix band:

- **S1** The CLI bypasses the `CANONICAL_CORPORATIONS` validation the API enforces, so a typo'd corporation writes rows invisible to every corporation-filtered metric.
- **S2** `Submission.source_file` stores a tempfile path (`/var/folders/…/tmpXXXX.csv`); `upload.filename` is available and discarded.
- **S3** All four migration tests run against an empty database, where the `e2b5c8d03f21` backfill loop is a no-op. The reviewer exercised it by hand against real rows and found it correct, but CI does not cover the branch's highest-risk operation.
- **S4** `SitrepModule` advertises `data_coverage`, which returns `[]` unconditionally. A report built from only that requirement yields zero facts and is marked `status: ok`, because the `empty_narrative` guard is gated on the fact table being non-empty.
- **S5** `/dmu/field-data` still advertises SITREP CSV upload, which now returns 400.
- **S6** `officer_name` / `officer_position` are written by the Survey123 path while `pii_columns_dropped` claims PII removal. Pre-existing on `main`, not a branch regression.
- **S7** `next_sequence_no` is an unguarded read-then-write.
- **S8** `RowErrorInfo.row_number` counts from the first data row, one off from what a corp sees in a spreadsheet. Promised as a docstring in an earlier task and never delivered.

Optional items: unused `create_submission`/`latest_submission`, the no-op `record_ids` slice, a prompt test asserting only a substring, `SENTENCE_SPLIT_RE` treating a bullet list as one sentence, the checker never binding a number to *its own* cid, and a sidebar page that never names the active corporation.

**Also noted:** the review did not read `dmu/reports/new.tsx`, the templates routes, or several new test bodies before it ran out of budget. That ground is unreviewed.
