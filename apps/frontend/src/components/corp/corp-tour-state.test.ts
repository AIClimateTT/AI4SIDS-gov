import { describe, expect, it } from 'vitest'

import {
  dismissTour,
  nextStop,
  rememberHomeSeen,
  resetTour,
  stepsForPage,
  tourPage,
  type TourStorage,
} from '@/components/corp/corp-tour-state'

function memory(): TourStorage {
  const values = new Map<string, string>()
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => {
      values.set(key, value)
    },
    removeItem: (key) => {
      values.delete(key)
    },
  }
}

describe('tour page', () => {
  it('treats the corporation home, including a trailing slash, as home', () => {
    expect(tourPage('/corp')).toBe('home')
    expect(tourPage('/corp/')).toBe('home')
  })

  it('treats an open conversation as the conversation', () => {
    expect(tourPage('/corp/c/1')).toBe('conversation')
  })

  it('ignores the print view and other corporation pages', () => {
    expect(tourPage('/corp/print/1')).toBe('other')
    expect(tourPage('/corp/events/4')).toBe('other')
  })
})

const HOME = ['home-resume', 'home-composer', 'tips']
const CONVERSATION = [
  'thread',
  'event',
  'facts',
  'situation',
  'records',
  'sitrep',
  'sitrep-view',
  'issue',
]

describe('steps for the page', () => {
  it('starts on home', () => {
    expect(stepsForPage('/corp', memory())).toEqual(HOME)
  })

  it('stays quiet on home once seen, and continues on a conversation', () => {
    const storage = memory()
    rememberHomeSeen(storage)
    expect(nextStop(storage)).toBe('conversation')
    expect(stepsForPage('/corp', storage)).toBeNull()
    expect(stepsForPage('/corp/c/8', storage)).toEqual(CONVERSATION)
  })

  it('shows the conversation part when a draft is opened before home', () => {
    expect(stepsForPage('/corp/c/3', memory())).toEqual(CONVERSATION)
  })

  it('stays quiet after the tour is dismissed, until it is reset', () => {
    const storage = memory()
    dismissTour(storage)
    expect(stepsForPage('/corp', storage)).toBeNull()
    expect(stepsForPage('/corp/c/3', storage)).toBeNull()
    resetTour(storage)
    expect(stepsForPage('/corp', storage)).toEqual(HOME)
  })
})
