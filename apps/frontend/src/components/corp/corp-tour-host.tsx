import { useRouterState } from '@tanstack/react-router'
import { useEffect, useState, useSyncExternalStore } from 'react'

import { startCorpTour } from '@/components/corp/corp-tour'
import {
  CORP_TOUR_RESTART,
  stepsForPage,
} from '@/components/corp/corp-tour-state'

const DESKTOP_TOUR = '(min-width: 768px)'

function subscribeDesktop(notify: () => void) {
  const media = window.matchMedia(DESKTOP_TOUR)
  media.addEventListener('change', notify)
  return () => media.removeEventListener('change', notify)
}

function desktopSnapshot() {
  return window.matchMedia(DESKTOP_TOUR).matches
}

function useDesktopTour() {
  return useSyncExternalStore(subscribeDesktop, desktopSnapshot, () => false)
}

const FIRST_SELECTOR: Record<string, string> = {
  'home-composer': '[data-tour="home-composer"]',
  facts: '[data-tour="facts"]',
}

/**
 * Starts the corporation walkthrough once the anchor is on the page, and
 * tears it down when the route changes. Narrow screens keep Tips, but the
 * Facts and Sitrep anchors sit behind View record, so the tour stays off.
 */
export function CorpTourHost() {
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  })
  const desktop = useDesktopTour()
  const [restart, setRestart] = useState(0)

  useEffect(() => {
    const onRestart = () => setRestart((count) => count + 1)
    window.addEventListener(CORP_TOUR_RESTART, onRestart)
    return () => window.removeEventListener(CORP_TOUR_RESTART, onRestart)
  }, [])

  useEffect(() => {
    if (!desktop) return
    const steps = stepsForPage(pathname)
    if (!steps) return
    const first = FIRST_SELECTOR[steps[0]]
    if (!first) return

    let cancelled = false
    let tour: { destroy: () => void } | null = null
    const begin = () => {
      if (cancelled || tour) return true
      if (!document.querySelector(first)) return false
      tour = startCorpTour(steps)
      return true
    }

    if (begin()) {
      return () => {
        cancelled = true
        tour?.destroy()
      }
    }

    const observer = new MutationObserver(() => {
      if (begin()) observer.disconnect()
    })
    observer.observe(document.body, { childList: true, subtree: true })
    return () => {
      cancelled = true
      observer.disconnect()
      tour?.destroy()
    }
  }, [desktop, pathname, restart])

  return null
}
