// @vitest-environment jsdom
import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import {
  SourceBadge,
  moduleDisplayName,
  sourceEdgeClass,
  sourceLabel,
  sourceOf,
} from './source-badge'

afterEach(() => {
  document.body.innerHTML = ''
})

describe('sourceOf', () => {
  it('recognises the two data modules', () => {
    expect(sourceOf('sitreps')).toBe('sitreps')
    expect(sourceOf('survey123')).toBe('survey123')
  })

  it('falls back to other for an unknown or missing module', () => {
    // A data module added backend-side must degrade to "labelled but unstyled",
    // never to a blank cell that reads as "no source".
    expect(sourceOf('rainfall_gauges')).toBe('other')
    expect(sourceOf(undefined)).toBe('other')
    expect(sourceOf('')).toBe('other')
  })
})

describe('sourceLabel', () => {
  it('labels the two sources distinctly', () => {
    expect(sourceLabel('sitreps')).toBe('Corporation')
    expect(sourceLabel('survey123')).toBe('Survey123')
    expect(sourceLabel('sitreps')).not.toBe(sourceLabel('survey123'))
  })
})

describe('moduleDisplayName', () => {
  it('keeps the short labels for known sources', () => {
    expect(moduleDisplayName('sitreps')).toBe('Corporation')
    expect(moduleDisplayName('survey123')).toBe('Survey123')
  })

  it('title-cases an unknown module instead of showing underscores', () => {
    expect(moduleDisplayName('rainfall_gauges')).toBe('Rainfall Gauges')
  })
})

describe('sourceEdgeClass', () => {
  it('gives the two sources different edge colours', () => {
    expect(sourceEdgeClass('sitreps')).not.toBe(sourceEdgeClass('survey123'))
  })

  it('returns a neutral edge for an unknown module', () => {
    expect(sourceEdgeClass('rainfall_gauges')).toBe('border-l-border')
  })
})

describe('SourceBadge', () => {
  it('calls corporation data what it is, and says it is unverified', () => {
    const { container } = render(<SourceBadge module="sitreps" />)
    expect(screen.getByText('Corporation')).toBeTruthy()
    expect(container.querySelector('[title]')?.getAttribute('title')).toContain(
      'unverified',
    )
  })

  it('renders the source as a word, not colour alone', () => {
    render(<SourceBadge module="survey123" />)
    expect(screen.getByText('Survey123')).toBeTruthy()
  })

  it('carries the authority of the source in its title', () => {
    const { container } = render(<SourceBadge module="survey123" />)
    // The distinction the whole architecture rests on has to be stated
    // somewhere a reader can reach without opening the docs.
    expect(container.querySelector('[title]')?.getAttribute('title')).toContain(
      'Verified by field staff',
    )
  })

  it('exposes the resolved source for styling and assertions', () => {
    const { container } = render(<SourceBadge module="sitreps" />)
    expect(container.querySelector('[data-source="sitreps"]')).not.toBeNull()
  })
})
