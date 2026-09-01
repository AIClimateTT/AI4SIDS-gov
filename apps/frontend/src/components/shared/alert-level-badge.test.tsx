// @vitest-environment jsdom
import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import {
  ALERT_LEVELS,
  AlertLevelBadge,
  alertSeverity,
  isAlertLevel,
} from './alert-level-badge'

afterEach(() => {
  document.body.innerHTML = ''
})

describe('AlertLevelBadge', () => {
  it('renders the level as text, not colour alone', () => {
    render(<AlertLevelBadge level="red" />)
    // The word is the accessible encoding; the colour is redundant. A screen
    // reader, a printed report and a monochrome display all get "Red".
    expect(screen.getByText('Red')).toBeTruthy()
  })

  it('renders every canonical level', () => {
    for (const level of ALERT_LEVELS) {
      const { unmount } = render(<AlertLevelBadge level={level} />)
      expect(screen.getByText(new RegExp(level, 'i'))).toBeTruthy()
      unmount()
    }
  })

  it('renders an unknown level legibly rather than blank', () => {
    // alert_level is typed as a bare string by the API, so a level added
    // backend-side before the frontend knows about it must still show.
    render(<AlertLevelBadge level="catastrophic" />)
    expect(screen.getByText('Catastrophic')).toBeTruthy()
  })

  it('exposes the raw level for testing and styling hooks', () => {
    const { container } = render(<AlertLevelBadge level="orange" />)
    expect(
      container.querySelector('[data-alert-level="orange"]'),
    ).not.toBeNull()
  })
})

describe('alertSeverity', () => {
  it('ranks red above every other level', () => {
    for (const level of ALERT_LEVELS) {
      if (level === 'red') continue
      expect(alertSeverity('red')).toBeGreaterThan(alertSeverity(level))
    }
  })

  it('ranks discontinued above green', () => {
    // A corporation that stood down reported something; one that was never
    // affected did not. The officer scanning the window wants the former first.
    expect(alertSeverity('discontinued')).toBeGreaterThan(
      alertSeverity('green'),
    )
  })

  it('ranks none lowest, because the level was never stated', () => {
    for (const level of ALERT_LEVELS) {
      if (level === 'none') continue
      expect(alertSeverity(level)).toBeGreaterThan(alertSeverity('none'))
    }
  })

  it('sorts an unknown level with none rather than throwing', () => {
    expect(alertSeverity('catastrophic')).toBe(alertSeverity('none'))
  })
})

describe('isAlertLevel', () => {
  it('accepts the six canonical values and rejects others', () => {
    for (const level of ALERT_LEVELS) expect(isAlertLevel(level)).toBe(true)
    expect(isAlertLevel('Red')).toBe(false)
    expect(isAlertLevel('')).toBe(false)
  })
})
