// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { CitationMarkdown } from '@/components/reports/citation-markdown'
import type { Fact } from '@/types/dmcu'

afterEach(() => {
  cleanup()
})

const factC001: Fact = {
  metric: 'incidents_by_corporation',
  value: 19,
  unit: 'incidents',
  scope: {},
  breakdown: null,
  verification: 'validated',
  citation: {
    cid: 'C001',
    module: 'sitreps',
    description: 'Signed-off incident count',
    query_ref: 'incidents_by_corporation()',
    record_ids: null,
    as_of: '2025-05-18T16:42:00Z',
  },
}

// The markdown rendered here is model-authored prose. rehype-raw parses its
// raw HTML so that the <mark> spans injected for violation highlighting work,
// which also meant anything else the model emitted rendered as live HTML.
//
// The <script> case is the one that actually reproduced against the shipped
// component; the attribute and javascript:-URL cases were already covered by
// react-markdown's own urlTransform and by React's attribute handling, and are
// kept as guards on the sanitize schema staying strict.

describe('CitationMarkdown', () => {
  it('does not execute or render a model-authored script tag', () => {
    const { container } = render(
      <CitationMarkdown
        markdown={'Incidents rose.\n\n<script>window.alert(1)</script>'}
      />,
    )

    expect(container.querySelector('script')).toBeNull()
    expect(container.innerHTML).not.toContain('window.alert')
  })

  it('strips an event-handler attribute from model-authored HTML', () => {
    const { container } = render(
      <CitationMarkdown
        markdown={'<img src="x" onerror="window.alert(1)" />'}
      />,
    )

    expect(container.innerHTML).not.toContain('onerror')
  })

  it('strips a javascript: link', () => {
    const { container } = render(
      <CitationMarkdown markdown={'<a href="javascript:alert(1)">click</a>'} />,
    )

    expect(container.innerHTML).not.toContain('javascript:')
  })

  it('still highlights a violation sentence with its mark class', () => {
    const { container } = render(
      <CitationMarkdown
        markdown="There were 99 incidents."
        violations={[
          {
            kind: 'invented_number',
            detail: 'no matching fact',
            sentence: 'There were 99 incidents.',
          },
        ]}
      />,
    )

    const mark = container.querySelector('mark')
    expect(mark).not.toBeNull()
    expect(mark?.getAttribute('class')).toContain('violation-mark')
  })

  it('still turns a citation marker into a clickable reference', () => {
    const { container } = render(
      <CitationMarkdown markdown="There were 19 incidents [C001]." />,
    )

    expect(container.querySelector('button')?.textContent).toBe('C001')
  })
})

describe('CitationMarkdown source identity', () => {
  const markdown =
    'Corporations reported 55 incidents [C001]. Field observation recorded 34 [C007].'

  it('tints each marker by the source of the fact it cites', () => {
    const { container } = render(
      <CitationMarkdown
        markdown={markdown}
        sourceByCid={{ C001: 'sitreps', C007: 'survey123' }}
      />,
    )
    expect(container.querySelector('[data-source="sitreps"]')).not.toBeNull()
    expect(container.querySelector('[data-source="survey123"]')).not.toBeNull()
  })

  it('states the source in words on each marker', () => {
    // Colour is redundant encoding. The marker is too small for a label, so the
    // title carries it.
    const { container } = render(
      <CitationMarkdown
        markdown={markdown}
        sourceByCid={{ C001: 'sitreps' }}
      />,
    )
    const marker = container.querySelector('[data-source="sitreps"]')
    expect(marker?.getAttribute('title')).toContain('SITREP')
  })

  it('falls back to neutral markers when no map is supplied', () => {
    const { container } = render(<CitationMarkdown markdown={markdown} />)
    expect(container.querySelector('[data-source="other"]')).not.toBeNull()
    expect(container.querySelector('[data-source="sitreps"]')).toBeNull()
  })
})

describe('CitationMarkdown readable citation', () => {
  it('opens the readable card instead of dumping the lookup string', () => {
    render(
      <CitationMarkdown
        markdown="There were 19 incidents [C001]."
        factsByCid={{ C001: factC001 }}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'C001' }))

    expect(screen.getByText('19 incidents')).toBeTruthy()
    expect(screen.getByText('Signed-off incident count')).toBeTruthy()
    expect(screen.queryByText('incidents_by_corporation()')).toBeNull()
    expect(screen.queryByText('query_ref')).toBeNull()
  })

  it('still jumps to the fact row from View in table', () => {
    const target = document.createElement('div')
    target.id = 'citation-C001'
    target.scrollIntoView = () => {
      target.dataset.scrolled = 'true'
    }
    document.body.appendChild(target)

    render(
      <CitationMarkdown
        markdown="There were 19 incidents [C001]."
        factsByCid={{ C001: factC001 }}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'C001' }))
    fireEvent.click(screen.getByRole('button', { name: 'View in table' }))

    expect(target.dataset.scrolled).toBe('true')
  })
})
