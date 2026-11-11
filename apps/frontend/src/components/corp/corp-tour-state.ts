export const CORP_TOUR_DISMISSED_KEY = 'corp-tour-dismissed'
export const CORP_TOUR_NEXT_KEY = 'corp-tour-next'
export const CORP_TOUR_RESTART = 'corp-tour-restart'
export const CORP_TOUR_SHOW_TAB = 'corp-tour-show-tab'

export type TourStorage = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>

export type TourStepId =
  | 'home-composer'
  | 'home-resume'
  | 'tips'
  | 'thread'
  | 'event'
  | 'facts'
  | 'situation'
  | 'records'
  | 'sitrep'
  | 'sitrep-view'
  | 'issue'

export type ArtifactTab = 'facts' | 'sitrep'

const HOME_STEPS: TourStepId[] = ['home-resume', 'home-composer', 'tips']

const CONVERSATION_STEPS: TourStepId[] = [
  'thread',
  'event',
  'facts',
  'situation',
  'records',
  'sitrep',
  'sitrep-view',
  'issue',
]

/** The anchor that must be on the page before that page's part can start. */
export const READY_SELECTOR = {
  home: '[data-tour="home-composer"]',
  conversation: '[data-tour="facts"]',
} as const

export function isTourDismissed(storage: TourStorage = localStorage): boolean {
  return storage.getItem(CORP_TOUR_DISMISSED_KEY) === '1'
}

export function dismissTour(storage: TourStorage = localStorage): void {
  storage.setItem(CORP_TOUR_DISMISSED_KEY, '1')
}

/** Home has been shown once; the next part is an open conversation. */
export function rememberHomeSeen(storage: TourStorage = localStorage): void {
  storage.setItem(CORP_TOUR_NEXT_KEY, 'conversation')
}

export function resetTour(storage: TourStorage = localStorage): void {
  storage.removeItem(CORP_TOUR_DISMISSED_KEY)
  storage.removeItem(CORP_TOUR_NEXT_KEY)
}

export function nextStop(
  storage: TourStorage = localStorage,
): 'conversation' | null {
  return storage.getItem(CORP_TOUR_NEXT_KEY) === 'conversation'
    ? 'conversation'
    : null
}

export function tourPage(pathname: string): 'home' | 'conversation' | 'other' {
  if (pathname.startsWith('/corp/print/')) return 'other'
  const path = pathname.replace(/\/+$/, '') || '/'
  if (path === '/corp') return 'home'
  if (path.startsWith('/corp/c/')) return 'conversation'
  return 'other'
}

/** Steps to show automatically. Null means stay quiet. */
export function stepsForPage(
  pathname: string,
  storage: TourStorage = localStorage,
): TourStepId[] | null {
  if (isTourDismissed(storage)) return null
  const page = tourPage(pathname)
  if (page === 'home') {
    if (nextStop(storage) === 'conversation') return null
    return HOME_STEPS
  }
  if (page === 'conversation') return CONVERSATION_STEPS
  return null
}

/** Replays the part for the current page, whatever was seen before. */
export function requestTourRestart(): void {
  resetTour()
  window.dispatchEvent(new Event(CORP_TOUR_RESTART))
}

/** Asks the record pane to show a tab without the side effects of a click,
 * so walking past the Sitrep tab never builds a draft. */
export function showArtifactTab(tab: ArtifactTab): void {
  window.dispatchEvent(
    new CustomEvent<ArtifactTab>(CORP_TOUR_SHOW_TAB, { detail: tab }),
  )
}
