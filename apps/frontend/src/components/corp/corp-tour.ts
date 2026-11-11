import { driver } from 'driver.js'
import type { DriveStep } from 'driver.js'

import {
  dismissTour,
  rememberFactsNext,
} from '@/components/corp/corp-tour-state'
import type { TourStepId } from '@/components/corp/corp-tour-state'

const COPY: Record<
  TourStepId,
  { title: string; description: string; side: 'top' | 'left' | 'bottom' }
> = {
  'home-composer': {
    title: 'Start a report',
    description: 'Type what is happening. Sending this opens the report.',
    side: 'bottom',
  },
  facts: {
    title: 'Facts',
    description: 'The report is built from this list.',
    side: 'bottom',
  },
  situation: {
    title: 'Situation',
    description:
      'Fill these if they are empty. An empty box is left out of the report.',
    side: 'left',
  },
  sitrep: {
    title: 'The report',
    description:
      'Final is the copy that will be sent. Draft may show short codes.',
    side: 'bottom',
  },
  issue: {
    title: 'Issue',
    description:
      'Press Issue when Final looks right. After that, this conversation cannot be changed.',
    side: 'top',
  },
}

const SELECTOR: Record<TourStepId, string> = {
  'home-composer': '[data-tour="home-composer"]',
  facts: '[data-tour="facts"]',
  situation: '[data-tour="situation"]',
  sitrep: '[data-tour="sitrep-tab"]',
  issue: '[data-tour="issue"]',
}

export function selectSitrepTab(): void {
  const tab = document.querySelector<HTMLElement>('[data-tour="sitrep-tab"]')
  if (!tab || tab.getAttribute('aria-selected') === 'true') return
  tab.click()
}

function shown(selector: string): HTMLElement | null {
  const node = document.querySelector<HTMLElement>(selector)
  if (!node || node.closest('[hidden]')) return null
  return node
}

function issueAnchor(): Element {
  selectSitrepTab()
  return (
    shown('[data-tour="issue"]') ??
    shown('[data-tour="sitrep-tab"]') ??
    document.body
  )
}

function toDriveStep(id: TourStepId): DriveStep {
  const copy = COPY[id]
  const step: DriveStep = {
    element: id === 'issue' ? issueAnchor : SELECTOR[id],
    popover: {
      title: copy.title,
      description: copy.description,
      side: copy.side,
      align: 'start',
    },
  }
  if (id === 'home-composer') step.data = { continueAt: 'facts' }
  if (id === 'sitrep' || id === 'issue') {
    step.onHighlightStarted = () => selectSitrepTab()
  }
  return step
}

export function startCorpTour(steps: TourStepId[]): { destroy: () => void } {
  if (steps[0] !== 'home-composer') rememberFactsNext()
  const tour = driver({
    animate: false,
    overlayOpacity: 0,
    overlayClickBehavior: 'none',
    stagePadding: 4,
    stageRadius: 8,
    popoverClass: 'corp-tour-popover',
    showProgress: steps.length > 1,
    nextBtnText: 'Next',
    prevBtnText: 'Back',
    doneBtnText: steps.length === 1 ? 'Next' : 'Done',
    showButtons: ['next', 'previous', 'close'],
    onPopoverRender: (popover, { driver: active }) => {
      if (popover.footerButtons.querySelector('.corp-tour-dismiss')) return
      const skip = document.createElement('button')
      skip.type = 'button'
      skip.className = 'driver-popover-footer-btn corp-tour-dismiss'
      skip.textContent = "Don't show again"
      skip.addEventListener('click', () => {
        dismissTour()
        active.destroy()
      })
      popover.footerButtons.prepend(skip)
    },
    onDestroyStarted: (_element, step, { driver: active, reason }) => {
      if (reason === 'done' && step.data?.continueAt === 'facts') {
        rememberFactsNext()
      } else if (
        reason === 'done' ||
        reason === 'close' ||
        reason === 'escape'
      ) {
        dismissTour()
      }
      active.destroy()
    },
    steps: steps.map(toDriveStep),
  })
  tour.drive()
  // The home composer moves down once the draft card arrives. Driver does not
  // notice that, so keep the popover next to the anchor while it is open.
  const anchor = SELECTOR[steps[0]]
  let lastTop = Number.NaN
  let frame = 0
  let passes = 0
  const watch = () => {
    passes += 1
    const node = document.querySelector(anchor)
    const top = node?.getBoundingClientRect().top
    const moved = top != null && Math.abs(top - lastTop) > 1
    // The first passes run after the popover has its real height. Measuring
    // before that pins it over the control.
    if ((moved || passes <= 4) && tour.isActive()) {
      if (top != null) lastTop = top
      tour.refresh()
    }
    frame = requestAnimationFrame(watch)
  }
  frame = requestAnimationFrame(watch)
  return {
    destroy() {
      cancelAnimationFrame(frame)
      tour.destroy()
    },
    isActive: () => tour.isActive(),
  }
}
