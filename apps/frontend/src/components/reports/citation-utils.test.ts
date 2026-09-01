import { describe, expect, it } from 'vitest'

import {
  linkifyCitations,
  markViolationSentences,
  normalizeCitationBrackets,
  repairReportStructure,
} from '@/components/reports/citation-utils'

describe('normalizeCitationBrackets', () => {
  it('converts the fullwidth brackets gpt-oss-20b writes', () => {
    // Reproduces the defect on report d6eb7218: fourteen markers in the prose,
    // none clickable, because U+3010/U+3011 look identical to [ ] on screen and
    // match nothing.
    expect(normalizeCitationBrackets('disruptions【C001】.')).toBe(
      'disruptions[C001].',
    )
  })

  it('converts the other bracket variants models reach for', () => {
    expect(normalizeCitationBrackets('［C002］')).toBe('[C002]')
    expect(normalizeCitationBrackets('〔C003〕')).toBe('[C003]')
  })

  it('leaves ASCII markers untouched', () => {
    expect(normalizeCitationBrackets('total [C001] were logged')).toBe(
      'total [C001] were logged',
    )
  })

  it('leaves fullwidth brackets that hold no citation alone', () => {
    const text = 'the 【important】 note'
    expect(normalizeCitationBrackets(text)).toBe(text)
  })
})

describe('linkifyCitations', () => {
  it('links a single ASCII marker', () => {
    expect(linkifyCitations('55 incidents [C001].')).toBe(
      '55 incidents [C001](#citation-C001).',
    )
  })

  it('links a fullwidth marker, which previously rendered as dead text', () => {
    expect(linkifyCitations('disruptions【C001】.')).toBe(
      'disruptions[C001](#citation-C001).',
    )
  })

  it('links every cid in a comma list', () => {
    // The backend checker has always accepted these; the frontend linked none.
    expect(linkifyCitations('no deaths [C003, C004].')).toBe(
      'no deaths [C003](#citation-C003), [C004](#citation-C004).',
    )
  })

  it('links both ends of an en-dash range', () => {
    // Observed live on report 51f7891b: "[C008–C013]" rendered unlinked even
    // though every other marker in that report worked.
    expect(linkifyCitations('validation rates [C008–C013].')).toBe(
      'validation rates [C008](#citation-C008)–[C013](#citation-C013).',
    )
  })

  it('links adjacent markers written back to back', () => {
    expect(linkifyCitations('recorded【C003】【C004】.')).toBe(
      'recorded[C003](#citation-C003)[C004](#citation-C004).',
    )
  })

  it('does not linkify a bracketed phrase that merely contains digits', () => {
    // The checker erases bracketed spans before scanning for figures, so a
    // bracket is not automatically a citation. Linking one would be worse: it
    // would imply a fact behind a number that has none.
    const text = 'Flooding affected [3,000 residents] across the region.'
    expect(linkifyCitations(text)).toBe(text)
  })

  it('leaves ordinary markdown links alone', () => {
    const text = 'see the [2024 flood report](http://example.test) for detail'
    expect(linkifyCitations(text)).toBe(text)
  })
})

describe('repairReportStructure', () => {
  it('promotes a bold-only line to a heading', () => {
    // Observed on a real report: seven section titles, all bold paragraphs, so
    // the document had no heading structure to navigate or style by.
    expect(repairReportStructure('**Casualties**\ntext')).toContain(
      '### Casualties',
    )
  })

  it('drops a trailing colon from a promoted heading', () => {
    expect(repairReportStructure('**Data Gaps:**')).toBe('### Data Gaps')
  })

  it('humanises a metric slug used as a section title', () => {
    // The renderer emits one per data table; a briefing carried eleven
    // snake_case database identifiers as headings.
    expect(repairReportStructure('**incidents_by_corporation**')).toBe(
      '### Incidents By Corporation',
    )
  })

  it('inserts the blank line a list needs to parse as a list', () => {
    // Without it markdown folds the bullets into the paragraph above and they
    // render as a literal "-" followed by text.
    const out = repairReportStructure('Some prose.\n- first\n- second')
    expect(out).toBe('Some prose.\n\n- first\n- second')
  })

  it('normalises bullet characters markdown does not recognise', () => {
    expect(repairReportStructure('Intro.\n• first')).toContain('- first')
  })

  it('leaves a correctly formed list alone', () => {
    const good = 'Some prose.\n\n- first\n- second'
    expect(repairReportStructure(good)).toBe(good)
  })

  it('leaves real headings and inline bold alone', () => {
    const good = '## Real Heading\n\nA sentence with **bold** inside it.'
    expect(repairReportStructure(good)).toBe(good)
  })

  it('is idempotent', () => {
    const input = '**Casualties**\n- one\n- two'
    const once = repairReportStructure(input)
    expect(repairReportStructure(once)).toBe(once)
  })
})

describe('markViolationSentences', () => {
  const v = (sentence: string) => ({ kind: 'invented_number', detail: '', sentence })

  it('does not nest marks when two violations share a sentence', () => {
    // Nested marks stack a translucent background, so the span rendered darker
    // than its neighbours and implied a severity the data does not carry.
    const out = markViolationSentences('A bad sentence here.', [
      v('A bad sentence here.'),
      v('A bad sentence here.'),
    ])
    expect(out.match(/<mark/g)).toHaveLength(1)
  })

  it('does not nest when one violation sentence contains another', () => {
    const out = markViolationSentences('The full sentence with detail.', [
      v('The full sentence with detail.'),
      v('full sentence'),
    ])
    expect(out.match(/<mark/g)).toHaveLength(1)
    expect(out).not.toContain('<mark class="violation-mark"><mark')
  })

  it('still marks two genuinely different sentences', () => {
    const out = markViolationSentences('First one. Second one.', [
      v('First one.'),
      v('Second one.'),
    ])
    expect(out.match(/<mark/g)).toHaveLength(2)
  })
})

describe('markViolationSentences on list items', () => {
  const v = (sentence: string) => ({ kind: 'invented_number', detail: '', sentence })

  it('keeps the list marker outside the mark so the line stays a list item', () => {
    // The checker splits on newlines, so a flagged bullet arrives as
    // "- 55 incidents ...". Wrapping the whole string put raw HTML at the start
    // of the line and markdown stopped parsing it as a list — the bullet
    // rendered as a literal hyphen inside a paragraph.
    const out = markViolationSentences('- 55 incidents were recorded.', [
      v('- 55 incidents were recorded.'),
    ])
    expect(out).toBe(
      '- <mark class="violation-mark">55 incidents were recorded.</mark>',
    )
    expect(out.startsWith('- ')).toBe(true)
  })

  it('handles an ordered list marker too', () => {
    const out = markViolationSentences('1. 55 incidents.', [v('1. 55 incidents.')])
    expect(out.startsWith('1. <mark')).toBe(true)
  })

  it('leaves a plain sentence wrapped as before', () => {
    const out = markViolationSentences('A plain sentence.', [v('A plain sentence.')])
    expect(out).toBe('<mark class="violation-mark">A plain sentence.</mark>')
  })
})
