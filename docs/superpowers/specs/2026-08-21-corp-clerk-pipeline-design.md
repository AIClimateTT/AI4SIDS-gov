# Corp Clerk Pipeline

**Date:** 2026-08-21
**Status:** Approved design, ready to implement
**Supersedes (corp report grain):** date-window `corp_situation_report` and `corp_sitrep_single` as two templates for one job
**Extends:** `docs/superpowers/specs/2026-07-26-corp-sitrep-realignment-design.md` (verbatim overview, logs as quantity+statement, minister reads sitrep *data*)

---

## 1. Problem

The corporation chat already captures a working set. The sitrep tab narrates from the wrong facts: incident follow-up flags instead of log quantities, a homes-affected metric that counts types not dwellings, and a thin `system_prompt` that never sees incident summaries. Two YAML templates share a title and disagree on params (date window vs submission). The DMU generate path can still produce a corporation report — leftover from when the DMU authored corp prose.

The product is a focused chat: pipeline in (officer utterance) → working set → pipeline out (issued sitrep). The DMU only generates minister reports from sitrep data, Survey123, and WhatsApp ingest.

## 2. Decisions

| # | Decision |
|---|---|
| 1 | One corp template: `corp_situation_report`. Params: `corporation` required, `submission_id` optional. Preview omits `submission_id`; Issue fills it. |
| 2 | Delete `corp_sitrep_single`. Demo data is not production: flush reports and templates, reimport. |
| 3 | DMU Generate offers only `minister_situation_report`. `field_data_region_review` stays in template admin. |
| 4 | Narration is `identity` + named `skills` (`capture`, `compose`). No `system_prompt` on templates. `LLMClient.generate(system_prompt=...)` is the chat-API role only. |
| 5 | Skills travel with the identity. Corp compose cannot affect minister compose. No `skills` table. |
| 6 | Capture JSON shape and canonical enums stay in Python. YAML is genre and contract. |
| 7 | Working set is the only number source between chat and report. Do not pass the transcript into narration. |
| 8 | Filing layout is deterministic tables + short connective prose. No MCP table tools. |
| 9 | Corp metrics drop `homes_affected_count` and `relief_actions_summary`. Relief comes from situation logs. |

## 3. Narration schema

```python
class NarrationSkills(BaseModel):
    capture: str = ""
    compose: str

class NarrationConfig(BaseModel):
    identity: str
    skills: NarrationSkills
    output_sections: list[str]
```

| Template | identity | capture | compose |
|---|---|---|---|
| `corp_situation_report` | corp clerk | yes | filing prose |
| `minister_situation_report` | minister writer | empty | national briefing |
| `field_data_region_review` | field-data reviewer | empty | Survey123 summary |

**Compose assembly:** `CITATION_RULES` + identity + `skills.compose`.

**Capture assembly:** identity + `skills.capture` + Python JSON/enum block.

## 4. Corp filing document

Renderer `layout: filing` (corp) vs `narrative` (minister / field-data).

1. Title + verbatim preamble (event, alert, as-at, overview, present activity). No untitled log bullets.
2. Situation summary from `incident_count.breakdown`.
3. Relief / stock from `relief_stock_summary`.
4. Incidents table from `incident_register`.
5. Activities from `activity_log`.
6. Connective prose from the LLM.
7. Data gaps from fact gaps + capture missing fields. Omit the section if empty; never print "None."
8. Citation appendix.

Omit zero-value facts and empty place cells (never "unknown street").

## 5. Metrics

Sitrep-only (not Survey123): `relief_stock_summary`, `activity_log`.

Incident: `incident_register` (one fact per row; scope holds date, community, street, type, summary, injuries, deaths, action).

Corp set: `incident_count`, `incident_register`, `casualty_summary`, `relief_stock_summary`, `activity_log`, `special_needs_count`, `estimated_damage_total`.

Working-set preview runs the same set on duck-typed incident and log rows.

## 6. Surfaces

- Capture turns, preview, and issue load `corp_situation_report`.
- CLI `generate corp_situation_report` exits: corp sitreps are issued from capture.
- Seed writes a minister report only, not date-window corp reports.

## 7. Out of scope

WhatsApp prompt rewrite, auth, sitrep streaming, minister metric set changes, MCP formatting, a skills table.
