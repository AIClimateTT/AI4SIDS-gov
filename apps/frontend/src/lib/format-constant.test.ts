import { describe, expect, it } from 'vitest'

import { formatConstant } from '@/lib/format-constant'

describe('formatConstant', () => {
  it('converts snake_case to Title Case', () => {
    expect(formatConstant('this_is_a_constant')).toBe('This Is A Constant')
  })

  it('handles single words', () => {
    expect(formatConstant('corporation')).toBe('Corporation')
  })

  it('ignores empty segments from repeated underscores', () => {
    expect(formatConstant('date__from')).toBe('Date From')
  })
})
