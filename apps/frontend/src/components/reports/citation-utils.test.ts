import { describe, expect, it } from 'vitest'

import {
  linkifyCitations,
  normalizeCitationBrackets,
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
