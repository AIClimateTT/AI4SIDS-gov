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

/** Escape a string for use in a RegExp. */
function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/**
 * Wrap violation sentences in <mark> tags for rehype-raw rendering.
 * Longer sentences first so nested/overlapping matches prefer the fuller span.
 */
export function markViolationSentences(
  markdown: string,
  violations: CitationViolation[],
): string {
  const sentences = violations
    // empty_narrative's sentence is an excerpt of the whole narrative, not a
    // flagged span — marking it would highlight the entire report.
    .filter((v) => v.kind !== 'empty_narrative')
    .map((v) => v.sentence?.trim())
    .filter((s): s is string => !!s && s.length > 0)
    .sort((a, b) => b.length - a.length)

  let result = markdown
  for (const sentence of sentences) {
    const pattern = new RegExp(escapeRegExp(sentence), 'g')
    result = result.replace(
      pattern,
      `<mark class="violation-mark">${sentence}</mark>`,
    )
  }
  return result
}

export function prepareReportMarkdown(
  markdown: string,
  violations: CitationViolation[],
): string {
  return linkifyCitations(markViolationSentences(markdown, violations))
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
