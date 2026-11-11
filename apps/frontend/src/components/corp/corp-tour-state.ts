export const CORP_TOUR_DISMISSED_KEY = 'corp-tour-dismissed'
export const CORP_TOUR_NEXT_KEY = 'corp-tour-next'
export const CORP_TOUR_RESTART = 'corp-tour-restart'

export type TourStorage = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>

export type TourStepId =
  'home-composer' | 'facts' | 'situation' | 'sitrep' | 'issue'

const CONVERSATION_STEPS: TourStepId[] = [
  'facts',
  'situation',
  'sitrep',
  'issue',
]

export function isTourDismissed(storage: TourStorage = localStorage): boolean {
  return storage.getItem(CORP_TOUR_DISMISSED_KEY) === '1'
}

export function dismissTour(storage: TourStorage = localStorage): void {
  storage.setItem(CORP_TOUR_DISMISSED_KEY, '1')
}

export function rememberFactsNext(storage: TourStorage = localStorage): void {
  storage.setItem(CORP_TOUR_NEXT_KEY, 'facts')
}

export function resetTour(storage: TourStorage = localStorage): void {
  storage.removeItem(CORP_TOUR_DISMISSED_KEY)
  storage.removeItem(CORP_TOUR_NEXT_KEY)
}

export function nextStop(storage: TourStorage = localStorage): 'facts' | null {
  return storage.getItem(CORP_TOUR_NEXT_KEY) === 'facts' ? 'facts' : null
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
    if (nextStop(storage) === 'facts') return null
    return ['home-composer']
  }
  if (page === 'conversation') return CONVERSATION_STEPS
  return null
}

export function requestTourRestart(): void {
  resetTour()
  window.dispatchEvent(new Event(CORP_TOUR_RESTART))
}
