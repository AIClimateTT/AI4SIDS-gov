import { describe, expect, it } from 'vitest'

import {
  dismissTour,
  nextStop,
  rememberFactsNext,
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

describe('steps for the page', () => {
  it('starts on the home composer', () => {
    expect(stepsForPage('/corp', memory())).toEqual(['home-composer'])
  })

  it('stays quiet on home after Next, and continues on a conversation', () => {
    const storage = memory()
    rememberFactsNext(storage)
    expect(nextStop(storage)).toBe('facts')
    expect(stepsForPage('/corp', storage)).toBeNull()
    expect(stepsForPage('/corp/c/8', storage)).toEqual([
      'facts',
      'situation',
      'sitrep',
      'issue',
    ])
  })

  it('starts at Facts when a draft is opened before home', () => {
    expect(stepsForPage('/corp/c/3', memory())).toEqual([
      'facts',
      'situation',
      'sitrep',
      'issue',
    ])
  })

  it('stays quiet after the tour is dismissed, until it is reset', () => {
    const storage = memory()
    dismissTour(storage)
    expect(stepsForPage('/corp', storage)).toBeNull()
    expect(stepsForPage('/corp/c/3', storage)).toBeNull()
    resetTour(storage)
    expect(stepsForPage('/corp', storage)).toEqual(['home-composer'])
  })
})
