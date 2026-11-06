# DMCU Reporting Flow

**Date:** 2026-10-29 (revised 2026-11-02 after stakeholder confirmation of Survey123's role)
**Status:** Agreed with stakeholder. The ArcGIS API connection is confirmed to exist; the hand-off of corporation incidents into Survey123 is future work.
**Supersedes:** Decision 6 of `docs/superpowers/specs/2026-07-26-corp-sitrep-realignment-design.md`
("validated Survey123 is corroboration" in the minister report). Survey123 is the verified source for its own reports. It is never mixed into the unverified corporation reports.

---

## 1. The problem this flow replaces

Corporations sent situation reports to the DMU as PDF/Word files in no fixed format
(`docs/examples/`), and sent quick updates through WhatsApp groups between reports. The DMU
re-typed both into the minister's report.

## 2. Three reports, two sources

| Report | Source | Status | LLM role | Used for |
|---|---|---|---|---|
| **A. Corporation sitrep** | Corporation capture | Unverified | None; matches the baselines | Hour-by-hour reporting during an event; replaces WhatsApp updates |
| **B. Minister sitrep** | Corporation data (the same records as A) | Unverified | None for now; bullets come from the officer's logs | The Minister's picture during an event, in the *Full Sitrep 2023* format |
| **C. Survey123 reports** | Survey123 | **Verified** by field staff before upload | **Full narration around computed numbers, citation-checked** | Post-action reporting for the Minister, and any further reporting the Ministry needs. New, with no baseline yet |

The LLM also stays in **capture**, where it turns the officer's message into structured records.

Survey123 data is verified by field staff before it is uploaded (stakeholder, 2026-11-02). Its
path, **Survey123 → Platform → Report generation**, is the most important layer for reporting.

## 3. Flow

```
 ┌──────────────────── UNVERIFIED · DURING THE EVENT (reports A and B) ──────────────────────┐
 │                                                                                            │
 │  ┌──────────────────────────┐                                                              │
 │  │ Corp point of contact    │  one per corporation (x14)                                   │
 │  └────────────┬─────────────┘                                                              │
 │               │ types / pastes / CSV — replaces both the PDF report and WhatsApp updates    │
 │               ▼                                                                            │
 │  ┌──────────────────────────────┐                                                          │
 │  │ CAPTURE INTERFACE (capture/) │  Event · Situation overview · Incidents · Situation logs │
 │  └──────────────┬───────────────┘                                                          │
 │                 │ issue → files a submission                                               │
 │                 ▼                                                                          │
 │  ╔══════════════════════════════╗                                                          │
 │  ║ SITREP STORE (sitreps/)      ║  events · submissions · sitrep_incidents · situation_logs │
 │  ╚═══════╤══════════════╤═══════╝                                                          │
 │          ▼              ▼                                                                  │
 │  ┌───────────────┐ ┌──────────────────────────────┐                                        │
 │  │ A. CORP       │ │ B. MINISTER SITREP           │                                        │
 │  │    SITREP     │ │    all 14 corps, §4.2        │                                        │
 │  │    §4.1       │ │                              │                                        │
 │  └───────────────┘ └──────────────────────────────┘                                        │
 └──────────┬─────────────────────────────────────────────────────────────────────────────────┘
            ┆ FUTURE: corporation incidents sent into Survey123 through the API, then verified
            ┆         there like any other record
            ▼
 ┌──────────────────── VERIFIED · SURVEY123 (report C) ──────────────────────────────────────┐
 │  ┌────────────────────────────────────────┐                                                │
 │  │ SURVEY123 / ArcGIS feature layer       │  field staff verify before upload              │
 │  └───────────────────┬────────────────────┘                                                │
 │                      │ today: CSV export + upload (survey123/)                             │
 │                      │ next:  ArcGIS API pull, verified records only                       │
 │                      ▼                                                                     │
 │  ╔══════════════════════════════╗       ┌────────────────────────────────┐                 │
 │  ║ FIELD STORE (survey123/)     ║──────►│ C. SURVEY123 REPORTS           │                 │
 │  ║ field_observations           ║       │ post-action (Minister) + other │                 │
 │  ╚══════════════════════════════╝       │ reporting needs                │                 │
 │                                         └────────────────────────────────┘                 │
 └────────────────────────────────────────────────────────────────────────────────────────────┘
```

Rules that follow:

- **WhatsApp is removed.** Capture replaces the reason corporations used WhatsApp.
- **Reports A and B read only the sitrep store. Report C reads only the field store.** The two
  sources are never combined in one figure or one report.
- **Report C is generated directly from the Field data page,** as a short report on the uploaded
  data. Today only the minister template can be generated, so Survey123 data uploaded alone
  produced a report saying "zero incidents" (§6).
- **A Survey123 file with any row not marked Validated is rejected whole.** A blank means the
  export was filtered wrongly. Nothing from that file is saved.
- **There is no module concept.** The system has two fixed sources: sitreps (unvalidated
  corporation incidents and logs) and Survey123 (verified, straight to report C).
- **The DMU has one table view of all corporation incidents and situation logs,** filterable by
  corporation and by filed report. Survey123 records stay on the Field data page.

## 4. Baseline formats

These come from the three stakeholder examples in `docs/examples/`. They are the quality
standard for reports A and B. Report C has no baseline yet.

### 4.1 Report A: corporation situation report

From *Borough of Diego Martin Situation Report #4* and *TPRC SITREP 18th May 2025*.

1. **Header block**
   - Title: `{HAZARD} SITUATION REPORT`, e.g. "ADVERSE WEATHER SITUATION REPORT".
   - Report number: "Situation Report #4".
   - As at: "As at 4:00 pm on 30/06/2023".
   - Location: the corporation.
   - Present Activity.
   - Alert Level, written out in full: "Localized Flooding Alert #2 – Yellow Level – extended
     until Mon 19th May, 2025 6pm" or "Discontinuation – Green Level".
2. **Situation Overview.** The officer's own words: which Met Office alert was issued and what it
   caused.
3. **Situation Summary.** Incident counts by type (Landslide 2, Roofing Damages 15…).
4. **Disaster Relief Distribution Summary.** Items *distributed* (Tarpaulins 18, Mattresses 3…).
5. **Summary of Activities.** Bullets (TPRC style).
6. **Incident register.** Numbered: No. | Date | Location | Description | Action Taken. The
   Action Taken column names referrals (Self-Help, MSDFS, Technical Dept., TTFS, CEPEP).
7. **Closing line.** "END OF REPORT", or "No further reports to be submitted" on the final
   report (alert discontinued).

The report contains no analysis and no narrative beyond the officer's overview.

### 4.2 Report B: minister situation report

From *Full Sitrep 2023*.

1. **Header block**
   - Title: `{HAZARD} SITUATION REPORT`.
   - As at.
   - Location: "Ministry of Rural Development and Local Government, Kent House".
   - Present Activity.
   - Alert Level.
2. **Situation Overview.** Written by the Ministry: the system's track and timing, and what it
   means nationally.
3. **One section per corporation, for all 14.** Bullets on what the corporation informed,
   prepositioned, inspected, filled or requested. A corporation that filed nothing reads
   "No reports at this time."
4. **Response from the Ministry.** What the Ministry itself did (e.g. a coordinators' meeting and
   its agenda).

The report has no incident tables and no Survey123 figures.

### 4.3 Report C: Survey123 reports

There is no baseline document yet. The first version is a short national summary, optionally for
one corporation (`survey123_summary`). Its format should be agreed with the stakeholder once they
have seen it run on their 2026 data.

## 5. Duplicates and re-uploads (Survey123)

Verified on the full export (15,221 rows):

- **Re-uploading the same or an overlapping period does not double-count.** Records are matched
  on Survey123's `GlobalID`. A second upload of the same file inserted 0 rows and updated 0. A
  record is only overwritten when its Survey123 `EditDate` is newer.
- **Same person, same event date** (same ID card number) is flagged as a duplicate and excluded
  from every count: 593 rows in the full export, 23 in 2026.
- **Known gaps:**
  - A record **deleted** in Survey123 stays in the platform, because an upload never deletes.
  - A record deleted and **re-entered** gets a new `GlobalID`, so it is counted twice unless it
    has the same ID number and date.

  The API pull should fix both by reading the layer's current state.

## 6. Incident log: "zero incidents" report and citation violations (2026-11-02)

- **Zero incidents.** The stakeholder uploaded Survey123 data for January 2026 onwards and
  generated the only report offered, `minister_situation_report`.
  - Its main figures come from corporation sitreps, and none had been filed, so they were all 0.
  - Survey123 (719 verified incidents for the period) was given to the model as corroboration
    only, so the model reported zero.
  - Fix: generate report C directly from the Field data page (§3).
- **Citation violations.** None of them was a wrong figure:
  - The model wrote dates with typographic dashes (`2026‑11‑02`), which the checker did not
    recognise as dates.
  - Numbered-list markers (`1.`) were read as figures.
  - "zero incidents" was correctly flagged as an uncited figure.
  - Fix: the checker accepts typographic dashes in dates and ignores list numbering.

## 7. Open questions

Resolved:

- **WhatsApp goes away.**
- **Validation:** field staff verify Survey123 records before upload, so uploaded data is treated
  as verified.
- **An ArcGIS API exists** and will be used to pull verified data.
- **Blank `Validated/NotValidated` values (2026-11-05):** the column must be filled. A blank means
  the export was filtered wrongly, and the whole file is rejected.
- **Templates (2026-11-05):** YAML files in code, with no page or table. The stakeholder gives
  feedback and the developer adjusts them. Each report records the template version that created
  it.
- **LLM role (2026-11-05):** none in reports A and B, full narration in report C, and it stays in
  capture (§2).

Still open:

1. **Report C format:** what should the Survey123 post-action report contain, and which other
   reports does the Ministry need from this data?
2. **Corp → Survey123 hand-off (future):** do situation logs go too, or only incidents? Is data
   sent on every submission or when the event closes? If a field correction and a later corp
   amendment conflict, which wins?
3. **Personal details:** the Diego Martin register lists names and phone numbers. This system
   strips them. Must report A, or the hand-off to Survey123, carry them, and is that permitted?
4. **ArcGIS access:** who owns the feature layer, and can we get a service account with read
   access (and later edit access)?
5. **Record identity (future hand-off):** our `record_ref` (`corp:event:row_id`) must be stored on
   the Survey123 feature so a returning record can be matched to the one sent. Is adding a field
   to the form acceptable?
6. **Report B incidents:** should each corporation's section also carry a one-line count of
   incidents by type during impact? The plan includes it, and it is easy to drop.
7. **Report B scope:** each corporation's latest submission within a date window, or a national
   event named by the DMU?
8. **Report B national summary:** should it open with a short generated paragraph? It is not in
   the 2023 baseline, so this is the stakeholder's call.
