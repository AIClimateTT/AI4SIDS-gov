// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { startCorpTour } from '@/components/corp/corp-tour'
import {
  CORP_TOUR_SHOW_TAB,
  isTourDismissed,
  nextStop,
  stepsForPage,
} from '@/components/corp/corp-tour-state'

let tour: { destroy: () => void } | null = null
let shownTabs: string[] = []
const onShow = (event: Event) => {
  shownTabs.push((event as CustomEvent<string>).detail)
}

// Node's own localStorage shadows jsdom's and is off without a backing file.
function memoryStorage(): Storage {
  const values = new Map<string, string>()
  return {
    get length() {
      return values.size
    },
    clear: () => values.clear(),
    getItem: (key) => values.get(key) ?? null,
    key: (index) => [...values.keys()][index] ?? null,
    removeItem: (key) => {
      values.delete(key)
    },
    setItem: (key, value) => {
      values.set(key, value)
    },
  }
}

beforeEach(() => {
  vi.stubGlobal('localStorage', memoryStorage())
  shownTabs = []
  window.addEventListener(CORP_TOUR_SHOW_TAB, onShow)
})

afterEach(() => {
  tour?.destroy()
  tour = null
  window.removeEventListener(CORP_TOUR_SHOW_TAB, onShow)
  document.body.innerHTML = ''
  vi.unstubAllGlobals()
})

function conversationPage({
  event = true,
  built = false,
}: { event?: boolean; built?: boolean } = {}) {
  document.body.innerHTML = `
    <div data-tour="thread-composer">composer</div>
    ${event ? '<section data-tour="event">confirm</section>' : ''}
    <button data-tour="facts">Facts</button>
    <button data-tour="sitrep-tab" data-sitrep="${built ? 'built' : 'none'}">Sitrep</button>
    <section data-tour="situation">situation</section>
    <div data-tour="records">incidents</div>
    ${
      built
        ? '<div data-tour="sitrep-view">toggle</div><button data-tour="issue">Issue</button>'
        : '<button data-tour="sitrep-generate">Generate draft</button>'
    }
  `
}

function homePage() {
  document.body.innerHTML = `
    <div data-tour="home-composer">composer</div>
    <button data-tour="tips">Tips</button>
  `
}

const title = () =>
  document.querySelector('.driver-popover-title')?.textContent ?? null
const progress = () =>
  document.querySelector('.driver-popover-progress-text')?.textContent ?? null
const press = (selector: string) =>
  document.querySelector<HTMLElement>(selector)?.click()
const next = () => press('.driver-popover-next-btn')

function walk(): string[] {
  const titles: string[] = []
  for (let i = 0; i < 20 && title(); i += 1) {
    titles.push(title()!)
    next()
  }
  return titles
}

describe('conversation tour', () => {
  it('walks every part of filing, in order', () => {
    conversationPage({ built: true })
    tour = startCorpTour('conversation', stepsForPage('/corp/c/1')!)
    expect(walk()).toEqual([
      'Keep the updates coming',
      'Confirm the event',
      'Facts',
      'Situation',
      'Incidents and logs',
      'Sitrep',
      'Draft and Final',
      'Issue',
    ])
  })

  it('moves between tabs without clicking the Sitrep tab', () => {
    conversationPage({ built: true })
    const click = vi.fn()
    document
      .querySelector('[data-tour="sitrep-tab"]')!
      .addEventListener('click', click)
    tour = startCorpTour('conversation', stepsForPage('/corp/c/1')!)
    walk()
    expect(click).not.toHaveBeenCalled()
    expect(shownTabs).toContain('sitrep')
    // Ending the tour puts the pane back on Facts.
    expect(shownTabs.at(-1)).toBe('facts')
  })

  it('leaves out the event step when the event is already confirmed', () => {
    conversationPage({ event: false, built: true })
    tour = startCorpTour('conversation', stepsForPage('/corp/c/1')!)
    expect(progress()).toBe('1 of 7')
    expect(walk()).not.toContain('Confirm the event')
  })

  it('points at Generate draft while there is no sitrep yet', () => {
    conversationPage({ built: false })
    tour = startCorpTour('conversation', stepsForPage('/corp/c/1')!)
    const titles = walk()
    expect(titles).toContain('Build the report')
    expect(titles).not.toContain('Draft and Final')
    expect(titles.at(-1)).toBe('Issue')
  })

  it('finishes the guide when it is closed', () => {
    conversationPage()
    tour = startCorpTour('conversation', stepsForPage('/corp/c/1')!)
    press('.driver-popover-close-btn')
    expect(title()).toBeNull()
    expect(isTourDismissed()).toBe(true)
  })
})

describe('home tour', () => {
  it('closing it moves on to the conversation part instead of ending the guide', () => {
    homePage()
    tour = startCorpTour('home', stepsForPage('/corp')!)
    expect(title()).toBe('Start a report')
    press('.driver-popover-close-btn')
    expect(title()).toBeNull()
    expect(isTourDismissed()).toBe(false)
    expect(nextStop()).toBe('conversation')
    expect(stepsForPage('/corp/c/1')).not.toBeNull()
  })

  it("Don't show again ends the whole guide", () => {
    homePage()
    tour = startCorpTour('home', stepsForPage('/corp')!)
    press('.corp-tour-dismiss')
    expect(title()).toBeNull()
    expect(isTourDismissed()).toBe(true)
    expect(stepsForPage('/corp/c/1')).toBeNull()
  })

  it('shows the unfiled draft first when there is one', () => {
    homePage()
    document.body.insertAdjacentHTML(
      'afterbegin',
      '<div data-tour="home-resume">draft</div>',
    )
    tour = startCorpTour('home', stepsForPage('/corp')!)
    expect(walk()).toEqual(['Unfiled draft', 'Start a report', 'Tips'])
  })
})
