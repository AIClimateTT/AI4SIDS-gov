# Making the Citation Checker Trustworthy

**Date:** 2026-08-03
**Status:** Approved design, ready for implementation planning
**Found by:** generating a real corp report and a real ministerial report against loaded demo data (see §1)

---

## 1. Problem

The citation checker is the system's central guarantee: every number in a generated report must trace to a computed fact. Running it end to end for the first time against real data showed the guarantee is not working as intended, in three distinct ways.

### 1.1 Every report is flagged, and none of the flags are real

A ministerial report generated over loaded data produced **13 violations**. Categorised:

| Flagged token | Count | Actually |
|---|---|---|
| `2023,` `2024` `31,` | 6 | Components of prose dates in the reporting period |
| `123` | 5 | Extracted from the word **"Survey123"** |
| missing_citation | 2 | On the engine's own generated data-gaps line |

Zero were hallucinated figures. Every real number — 15, 13, 1, 8, 12, 4, 115800, 19, 10, 6, 50%, 80%, 66.7%, 100% — was correctly cited. The corp report showed the same pattern: 3 violations, all date components.

Two root causes in `app/core/citation_check.py`:

- `NUMBER_TOKEN_RE = r"\d[\d,]*(?:\.\d+)?%?"` has **no word boundary**, so it matches the `123` inside `Survey123`. The system's own module name trips its own checker, and it does so more often the more carefully a template asks the model to name its sources.
- `_strip_dates` removes only **ISO** dates via `ISO_DATE_RE`. Prose dates — "June 1, 2023", "August 3rd, 2026", "December 31, 2024" — pass straight through and their year and day components are read as figures.

**Why this matters more than the count suggests.** A check that fires on every report trains reviewers to dismiss it. `needs_review` currently carries no information, so the one signal that would catch a genuine hallucination is the signal people learn to ignore.

### 1.2 An empty narrative passes as `ok`

A ministerial report over a wider window produced a narrative of exactly `**` — the model returned nothing usable. The checker passed it: no sentences means no number tokens means no violations, so `passed=True` and the report was written with `status: ok`.

A report with no prose and a clean status is worse than a good report flagged for review, because nothing about it invites a second look.

### 1.3 The cause of 1.2: Ollama silently truncates at 2048 tokens

`OllamaLLMClient` (`app/core/llm.py`) constructs `ChatOllama(base_url=..., model=...)` and never sets `num_ctx`. Ollama's default context is 2048 tokens. Measured payloads for the same template:

| Window | Facts | Fact-table JSON | Approx tokens | Result |
|---|---|---|---|---|
| 2023-06 only | 7 | 5,602 chars | ~1,400 | narrative produced |
| 2023-06 → 2024-12 | 11 | 8,198 chars | ~2,049 | empty narrative |

Plus the system prompt, the wider window crosses 2048 and output collapses. Switching to a model built with a larger context (`gemma3-12b-16k`) produced a correct narrative immediately, confirming the diagnosis.

This is a silent failure at exactly the wrong moment: fact tables grow as more corporations report, so the system breaks precisely as it starts being used for real.

### 1.4 Known and accepted: spelled-out numbers evade entirely

An earlier ministerial report wrote *"Fifteen incidents were reported… Thirteen homes were affected… One injury was recorded"*. The checker scans digits, so none of these were examined. This is a demonstrated evasion path.

---

## 2. Decisions

| # | Decision | Rationale |
|---|---|---|
| 1 | **Fix precision with a word boundary and prose-date stripping. Excuse nothing else.** | Targets the two demonstrated causes without inventing broad exemptions. Rejected: excusing any 4-digit number in 1900–2100, because this system reports damage costs in TTD where 2000 is a plausible figure. |
| 2 | **A narrative citing nothing, while facts exist, is a violation.** | That is a generation failure, not a report. Rejected: requiring every fact to be cited (fails legitimate reports); raising an error (discards the deterministic fact tables, which are the useful part). |
| 3 | **Set `num_ctx` explicitly, defaulting to 8192.** | Fixes the cause of §1.2. Decision 2 catches the symptom whatever the cause — both are done deliberately. |
| 4 | **Require digits in the prompt; do not detect number words.** | `CITATION_RULES` already prepends to every template prompt, so this costs one line. Detection is rejected because the common number words are too ambiguous in prose — "two of the fourteen corporations" would trip it, recreating the alarm fatigue this work exists to remove. |

### Accepted cost, stated plainly

**Decision 1 makes the checker more permissive by construction.** Today it flags everything; afterwards it flags less. A genuine figure sitting inside a date-shaped phrase — "the 2023 homes affected" — would be stripped and go unchecked. This is a real hole, judged smaller than a 100% false-positive rate that renders the check meaningless. It is a deliberate trade, not an oversight.

**Decision 4 narrows rather than closes §1.4.** A model that ignores the instruction can still spell figures and evade the checker entirely.

---

## 3. Checker precision

`app/core/citation_check.py`.

**Word boundary.** `NUMBER_TOKEN_RE` becomes `\b\d[\d,]*(?:\.\d+)?%?` so a digit run preceded by a word character is not matched. `Survey123` yields nothing; `survey123.data_coverage` yields nothing; `15` and `66.7%` and `115,800` still match.

**Prose dates.** A new pattern strips, before tokenising and alongside the existing ISO stripping:

- `June 1, 2023` / `Jun 1 2023` — month name, day, optional comma, 4-digit year
- `August 3rd, 2026` — the same with an ordinal suffix (`st`, `nd`, `rd`, `th`)
- `31 December 2024` — day-first
- A bare 4-digit year **only** when directly adjacent to a month name (`June 2023`)

A bare year with no month is **not** stripped. `2023` alone in a sentence remains checkable, because it is indistinguishable from a figure without surrounding context.

Both strippers run over a copy used solely for number extraction. The sentence stored on a violation stays the original, so a reviewer sees what was actually written.

---

## 4. Empty-narrative violation

`CitationViolation.kind` gains `"empty_narrative"`.

After sentence iteration, if the fact table holds at least one fact **and** no sentence carried a citation marker matching a fact's `cid`, append one violation of this kind. One violation, not one per fact. Its `sentence` field carries the narrative's first 200 characters (the whole thing when shorter), which is enough for a reviewer to see that nothing was written without pasting a full report into a violation record.

**Downstream note:** `CitationViolation.kind` is a `Literal`, and the frontend renders violations in `src/components/reports/violations-panel.tsx` and highlights them via `citation-utils.ts`. Check both handle an unrecognised kind by falling back to `detail` rather than assuming the existing two — a new kind must not blank the panel.

The condition is deliberately "cited nothing", not "wrote nothing": a narrative of prose that happens to name no citation is equally a failure to report, and catching both with one rule is simpler than special-casing whitespace.

`generate_report` already retries once when `check_citations` fails, so this earns a degenerate generation a second attempt at no extra design cost. If the retry also fails, the report is saved `needs_review` with the fact tables intact.

---

## 5. Ollama context

`app/config.py` gains `ollama_num_ctx: int = 8192`.

`OllamaLLMClient.__init__` passes it: `ChatOllama(base_url=..., model=..., num_ctx=...)`. The existing injected-`chat` parameter is unchanged, so tests that pass a fake client are unaffected.

8192 is chosen as comfortably above the largest measured payload (~2,049 tokens) with room for growth as corporations are added, while remaining runnable on the models installed here. It is a setting rather than a constant so it can be raised without a code change when fact tables grow.

**Not in scope:** sizing `num_ctx` dynamically from the payload, or failing when a payload would exceed it. Decision 2 already converts that failure from silent to visible, which is the property that matters.

---

## 6. Prompt rule

`CITATION_RULES` in `app/core/engine.py` gains one line:

> Write every figure as digits, never words — "15", not "fifteen".

It joins the existing absolute rules, so it applies to every template without touching any template.

---

## 7. Testing

The regression cases are taken verbatim from the real generated output, so they encode the actual failures rather than imagined ones.

**Precision — must NOT flag:**
- A sentence containing `Survey123` with no other digits produces no violation.
- `survey123.data_coverage` in a data-gaps line produces no `invented_number`.
- "from June 1, 2023, to December 31, 2024" produces no violation.
- "As of August 3rd, 2026," produces no violation.
- An ISO date still produces no violation (guards the existing behaviour).

**Precision — must STILL flag:**
- A cited sentence containing a number absent from the fact table still produces `invented_number`. This is the test that proves the fix did not simply disable the check.
- A bare 4-digit year with no adjacent month is still checked.
- A sentence with a figure and no citation marker still produces `missing_citation`.

**Empty narrative:**
- A narrative of `**` against a non-empty fact table produces exactly one `empty_narrative` violation and `passed=False`.
- An empty string does the same.
- A narrative citing at least one valid `cid` produces no `empty_narrative` violation.
- An empty narrative against an **empty** fact table produces none — there was nothing to report.

**Ollama:**
- `OllamaLLMClient` constructs its `ChatOllama` with `num_ctx` from settings. Asserted without a network call.

**End to end:** regenerate the corp report against the demo data and confirm it reaches `status: ok`. This is the real acceptance criterion — the report whose 3 violations were all false positives should now pass.

---

## 8. Out of scope

- Detecting spelled-out numbers (§1.4) — mitigated by the prompt rule, residual risk documented.
- Dynamic `num_ctx` sizing or pre-flight payload rejection.
- The two pre-existing `tests/test_llm.py` failures, caused by leftover Cursor debug instrumentation in `app/core/llm.py` and `app/api/reports.py`. That instrumentation writes to a hardcoded absolute path and is unrelated to this work, but note that §5 modifies the same file — whoever does this will be reading around it.
