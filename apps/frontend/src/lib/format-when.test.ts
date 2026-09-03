import { describe, expect, it } from 'vitest'

import { formatDay, formatWhen } from '@/lib/format-when'

describe('formatWhen', () => {
  it('drops the seconds nobody files to', () => {
    // "6/30/2023, 4:00:00 PM" was what every call site rendered.
    expect(formatWhen('2023-06-30T16:00:00')).not.toContain(':00:00')
  })

  it('uses a 24-hour clock so two filings do not read alike', () => {
    // 04:00 and 16:00 both rendered as "4:00" plus a meridiem an officer has
    // to notice; on a 24-hour clock they cannot be confused.
    expect(formatWhen('2023-06-30T16:00:00')).toContain('16:00')
    expect(formatWhen('2023-06-30T04:00:00')).toContain('04:00')
  })

  it('names the month rather than numbering it', () => {
    // 6/30 vs 30/6 depends on where the reader is from; "Jun" does not.
    expect(formatWhen('2023-06-30T16:00:00')).toContain('Jun')
  })

  it('renders an em dash for a missing timestamp', () => {
    expect(formatWhen(null)).toBe('—')
    expect(formatWhen(undefined)).toBe('—')
    expect(formatWhen('')).toBe('—')
  })

  it('renders an em dash rather than echoing an unparseable one', () => {
    expect(formatWhen('not a date')).toBe('—')
  })
})

describe('formatDay', () => {
  it('omits the time', () => {
    const out = formatDay('2023-06-30T16:00:00')
    expect(out).toContain('Jun')
    expect(out).not.toContain('16')
  })

  it('renders an em dash for a missing day', () => {
    expect(formatDay(null)).toBe('—')
  })
})
