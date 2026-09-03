import { formatConstant } from '@/lib/format-constant'
import type { CitationViolation, Fact } from '@/types/dmcu'

/**
 * Bracket characters models actually use, mapped back to ASCII.
 *
 * gpt-oss-20b writes citations as `【C001】` (U+3010/U+3011), not `[C001]`.
 * The two are indistinguishable on screen and completely different to a regex,
 * so every marker in such a report rendered as dead text while a visually
 * identical report from another model linked correctly. Observed on report
 * d6eb7218 — fourteen fullwidth markers, zero clickable — against 51f7891b,
 * whose model wrote ASCII and linked all twenty-two.
 *
 * Normalising here rather than at each call site means the checker-facing and
 * reader-facing paths agree on what a marker is.
 */
const BRACKET_VARIANTS_RE =
  /[【［〔〖]\s*((?:C\d{3}[\s,–—-]*)+?)\s*[】］〕〗]/g

export function normalizeCitationBrackets(markdown: string): string {
  return markdown.replace(BRACKET_VARIANTS_RE, (_match, inner: string) => {
    return `[${inner.trim()}]`
  })
}

/**
 * A bracket holding one or more cids, however they are separated.
 *
 * Single `[C001]` is the common case, but a model citing several facts writes
 * `[C001, C002]`, and one citing a run writes `[C008–C013]` with an en-dash.
 * The backend checker has always accepted comma lists; the frontend linked
 * neither, so a correctly-cited sentence rendered with no working markers.
 * Only cids and separators are allowed inside, so `[3,000 residents]` is left
 * alone.
 */
const CITATION_GROUP_RE = /\[((?:\s*C\d{3}\s*[,–—-]?)+)\]/g
const CID_RE = /C\d{3}/g

/** Convert citation markers into markdown links targeting fact-table anchors. */
export function linkifyCitations(markdown: string): string {
  return normalizeCitationBrackets(markdown).replace(
    CITATION_GROUP_RE,
    (_match, inner: string) =>
      // Each cid becomes its own link; separators survive between them, so
      // "C008–C013" still reads as a range with both ends reachable.
      inner.replace(CID_RE, (cid) => `[${cid}](#citation-${cid})`),
  )
}

/**
 * Repair the markdown structure models actually emit.
 *
 * Every model writes markdown differently and the system has to render all of
 * them — the narration prompt can be tightened for one model, but the next one
 * has its own habits, and the deployed model is not always the one available to
 * develop against. This function is the single place that sees whatever arrived
 * and makes it a document.
 *
 * Two defects observed on a real ministerial report:
 *
 * 1. Section titles written as a bold paragraph rather than a heading. The
 *    briefing had seven sections and one `<h1>` plus two `<h2>` between them —
 *    nothing to navigate by, and every section title rendered at body size.
 * 2. A list glued to the line above it. Markdown needs a blank line before a
 *    list; without one the whole block is one paragraph and the bullets render
 *    as a literal "-" followed by text. That report had eighteen such lines
 *    against thirteen real list items.
 *
 * Both repairs are idempotent and leave well-formed markdown untouched.
 */

/** A line that is nothing but bold text, optionally ending in a colon. */
const BOLD_ONLY_LINE_RE = /^\s*\*\*(.+?)\*\*\s*:?\s*$/
/** Bullet markers models reach for, including the ones markdown does not know. */
const BULLET_LINE_RE = /^\s*(?:[-*+]|•|·|‣)\s+\S/
const HEADING_LINE_RE = /^\s*#{1,6}\s/

function isBullet(line: string): boolean {
  return BULLET_LINE_RE.test(line)
}

/**
 * A metric identifier used as a section title, e.g. `incidents_by_corporation`.
 *
 * The renderer emits one per data table, so a ministerial briefing carried
 * eleven snake_case database identifiers as headings — `data_coverage` six
 * times over. `formatConstant` is the same helper the rest of the interface
 * uses to turn a constant into a label.
 */
const METRIC_SLUG_RE = /^[a-z][a-z0-9]*(?:_[a-z0-9]+)+$/

function humaniseTitle(title: string): string {
  // A trailing colon can sit inside the bold (`**Data Gaps:**`) or outside it
  // (`**Data Gaps**:`); models write both, and neither belongs in a heading.
  const trimmed = title.replace(/\s*:\s*$/, '')
  return METRIC_SLUG_RE.test(trimmed) ? formatConstant(trimmed) : trimmed
}

export function repairReportStructure(markdown: string): string {
  const lines = markdown.split('\n')
  const out: string[] = []

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]

    // A standalone bold line is a heading doing the wrong job. h3 rather than
    // h2: the report's own title is the h1 and "Data Tables" is an h2, so these
    // sit beneath both.
    const bold = BOLD_ONLY_LINE_RE.exec(line)
    if (bold && bold[1].trim().length > 0) {
      // Blank line before a heading, or the previous paragraph absorbs it.
      if (out.length > 0 && out[out.length - 1].trim() !== '') out.push('')
      out.push(`### ${humaniseTitle(bold[1].trim())}`)
      continue
    }

    // Normalise the bullet character so remark sees a list at all.
    const normalised = isBullet(line)
      ? line.replace(/^(\s*)(?:•|·|‣)(\s+)/, '$1-$2')
      : line

    // A list that starts immediately under a non-blank, non-list line needs a
    // blank line inserted or markdown folds it into that paragraph.
    if (isBullet(normalised) && out.length > 0) {
      const prev = out[out.length - 1]
      if (prev.trim() !== '' && !isBullet(prev) && !HEADING_LINE_RE.test(prev)) {
        out.push('')
      }
    }

    out.push(normalised)
  }

  return out.join('\n')
}

/** Escape a string for use in a RegExp. */
function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/** A bullet or ordered-list marker at the start of a flagged sentence. */
const LIST_MARKER_PREFIX_RE = /^(\s*(?:[-*+]|\d+\.)\s+)([\s\S]+)$/

/**
 * Wrap violation sentences in <mark> tags for rehype-raw rendering.
 *
 * Longest first, and a sentence already contained in a longer one is dropped
 * rather than wrapped again. Two violations on the same sentence — an
 * `invented_number` and a `missing_citation`, say — used to produce
 * `<mark><mark>…</mark></mark>`, and because the highlight is a translucent
 * background the doubled span rendered visibly darker than its neighbours.
 * A reader has no way to know that means "two violations here" rather than
 * "worse violation here", so it read as emphasis the data does not support.
 */
export function markViolationSentences(
  markdown: string,
  violations: CitationViolation[],
): string {
  const ordered = violations
    // empty_narrative's sentence is an excerpt of the whole narrative, not a
    // flagged span — marking it would highlight the entire report.
    .filter((v) => v.kind !== 'empty_narrative')
    .map((v) => v.sentence?.trim())
    .filter((s): s is string => !!s && s.length > 0)
    .sort((a, b) => b.length - a.length)

  const sentences: string[] = []
  for (const sentence of ordered) {
    // Longest-first means any container is already accepted, so containment
    // against what we have kept is enough — and it also drops exact duplicates.
    if (sentences.some((kept) => kept.includes(sentence))) continue
    sentences.push(sentence)
  }

  let result = markdown
  for (const sentence of sentences) {
    const pattern = new RegExp(escapeRegExp(sentence), 'g')
    result = result.replace(pattern, (match) => {
      // The checker splits on newlines, so a flagged list item arrives with its
      // "- " still attached. Wrapping that whole string puts raw HTML at the
      // start of the line, markdown stops seeing a list item, and the bullet
      // renders as a literal hyphen in a paragraph. Keep the marker outside the
      // mark so the line still begins with it.
      const withMarker = LIST_MARKER_PREFIX_RE.exec(match)
      if (withMarker) {
        return `${withMarker[1]}<mark class="violation-mark">${withMarker[2]}</mark>`
      }
      return `<mark class="violation-mark">${match}</mark>`
    })
  }
  return result
}

/**
 * Order matters. Structure is repaired first, on the model's own text, so the
 * heading and list rules see the lines as written. Violation marks go on next,
 * because they match against sentences the checker recorded — which are also
 * the model's own text, before any link markup exists. Citations link last, so
 * a marker inside a marked sentence still becomes a working link.
 */
export function prepareReportMarkdown(
  markdown: string,
  violations: CitationViolation[],
): string {
  const repaired = repairReportStructure(markdown)
  return linkifyCitations(markViolationSentences(repaired, violations))
}

export function citationAnchorId(cid: string): string {
  return `citation-${cid}`
}

export function scrollToCitation(cid: string): void {
  const el = document.getElementById(citationAnchorId(cid))
  if (!el) return

  el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  el.classList.remove('citation-flash')
  // Restart animation
  void el.offsetWidth
  el.classList.add('citation-flash')
  window.setTimeout(() => {
    el.classList.remove('citation-flash')
  }, 1400)
}

export function getFacts(facts: Fact[] | undefined): Fact[] {
  return facts ?? []
}
