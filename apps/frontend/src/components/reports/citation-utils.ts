import type { CitationViolation, Fact } from '@/types/dmcu'

const CITATION_REF_RE = /\[(C\d{3})\]/g

/** Convert [C001] markers into markdown links targeting fact-table anchors. */
export function linkifyCitations(markdown: string): string {
  return markdown.replace(CITATION_REF_RE, '[$1](#citation-$1)')
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
