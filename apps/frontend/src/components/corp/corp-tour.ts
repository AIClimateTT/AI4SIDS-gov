import { driver } from 'driver.js'
import type { DriveStep, Side } from 'driver.js'

import {
  dismissTour,
  rememberHomeSeen,
  showArtifactTab,
} from '@/components/corp/corp-tour-state'
import type { ArtifactTab, TourStepId } from '@/components/corp/corp-tour-state'

type Copy = { title: string; description: string; side: Side }

type StepSpec = {
  selector: string
  copy: Copy
  /** Tab the record pane must show for the anchor to be on the page. */
  tab?: ArtifactTab
  /** Left out when the anchor is absent at the start, e.g. no event to
   * confirm, so the step count stays honest. */
  optional?: boolean
  /** Used instead while the conversation has no sitrep draft yet, since the
   * view toggle and Issue only appear once one is built. */
  unbuilt?: { selector: string; copy: Copy }
}

const SPECS: Record<TourStepId, StepSpec> = {
  'home-composer': {
    selector: '[data-tour="home-composer"]',
    copy: {
      title: 'Start a report',
      description:
        'Type what is happening in ordinary sentences: the alert, where, what was damaged, injuries, deaths, and what the corporation has done. Sending it opens the conversation for this report.',
      side: 'bottom',
    },
  },
  'home-resume': {
    selector: '[data-tour="home-resume"]',
    optional: true,
    copy: {
      title: 'Unfiled draft',
      description:
        'A report you started and have not issued. Press Resume to carry on with it instead of starting a new one.',
      side: 'bottom',
    },
  },
  tips: {
    selector: '[data-tour="tips"]',
    copy: {
      title: 'Tips',
      description:
        'The filing rules are kept here. Press Show me around to see this guide again at any time.',
      side: 'right',
    },
  },
  thread: {
    selector: '[data-tour="thread-composer"]',
    copy: {
      title: 'Keep the updates coming',
      description:
        'Add more updates here, or correct a figure with a new message ("change the sandbags to 20"). If the reply says it could not read the update, send it again in a shorter sentence. Press + to upload an incidents or situation logs CSV.',
      side: 'top',
    },
  },
  event: {
    selector: '[data-tour="event"]',
    optional: true,
    copy: {
      title: 'Confirm the event',
      description:
        'Press This is part of for an event that is already running, or type the title, choose the hazard and start date, and press Confirm event. A report with incidents cannot be issued until this is done.',
      side: 'top',
    },
  },
  facts: {
    selector: '[data-tour="facts"]',
    tab: 'facts',
    copy: {
      title: 'Facts',
      description:
        'The report is built only from this list. Check it after each message you send.',
      side: 'bottom',
    },
  },
  situation: {
    selector: '[data-tour="situation"]',
    tab: 'facts',
    copy: {
      title: 'Situation',
      description:
        'Check Situation overview, Alert wording and Present activity. Type them if they are empty: an empty box is left off the report. What you type stays as you typed it.',
      side: 'left',
    },
  },
  records: {
    selector: '[data-tour="records"]',
    tab: 'facts',
    copy: {
      title: 'Incidents and logs',
      description:
        'The count here is what will be reported. If you described three incidents and see one, send the others again or press + Add manually. Use Edit to correct a row and Remove to drop one.',
      side: 'left',
    },
  },
  sitrep: {
    selector: '[data-tour="sitrep-tab"]',
    tab: 'sitrep',
    copy: {
      title: 'Sitrep',
      description:
        'Open this when Facts look right. If you change Facts afterwards it says the facts changed: press Refresh, then read Final again.',
      side: 'bottom',
    },
  },
  'sitrep-view': {
    selector: '[data-tour="sitrep-view"]',
    tab: 'sitrep',
    copy: {
      title: 'Draft and Final',
      description:
        'Draft is for checking and may show short codes beside figures. Final is the report that will be sent. Read Final.',
      side: 'bottom',
    },
    unbuilt: {
      selector: '[data-tour="sitrep-generate"]',
      copy: {
        title: 'Build the report',
        description:
          'When Facts look right, press Generate draft. The report is built from Facts, and you can then switch between Draft and Final.',
        side: 'top',
      },
    },
  },
  issue: {
    selector: '[data-tour="issue"]',
    tab: 'sitrep',
    copy: {
      title: 'Issue',
      description:
        'Press Issue when Final is right. The conversation then closes and cannot be changed. A correction is a new report from Home.',
      side: 'top',
    },
    unbuilt: {
      selector: '[data-tour="sitrep-tab"]',
      copy: {
        title: 'Issue',
        description:
          'Once the report is built, Issue is at the bottom of this tab. Press it when Final is right. The conversation then closes; a correction is a new report from Home.',
        side: 'bottom',
      },
    },
  },
}

function shown(selector: string): HTMLElement | null {
  const node = document.querySelector<HTMLElement>(selector)
  if (!node || node.closest('[hidden]')) return null
  return node
}

function sitrepBuilt(): boolean {
  return (
    document
      .querySelector('[data-tour="sitrep-tab"]')
      ?.getAttribute('data-sitrep') === 'built'
  )
}

function toDriveStep(id: TourStepId, built: boolean): DriveStep {
  const spec = SPECS[id]
  const { selector, copy } = spec.unbuilt && !built ? spec.unbuilt : spec
  return {
    element: () => {
      if (spec.tab) showArtifactTab(spec.tab)
      // Driver's type wants an element, but a missing one is what
      // skipMissingElement checks for, so null skips the step.
      return shown(selector) as Element
    },
    popover: {
      title: copy.title,
      description: copy.description,
      side: copy.side,
      align: 'start',
    },
  }
}

export function startCorpTour(
  page: 'home' | 'conversation',
  steps: TourStepId[],
): { destroy: () => void } {
  // Home is a single look. Leaving it, by Done or by sending a message,
  // moves the guide on to the conversation part.
  if (page === 'home') rememberHomeSeen()
  const built = sitrepBuilt()
  const present = steps.filter(
    (id) => !SPECS[id].optional || shown(SPECS[id].selector),
  )
  let frame = 0
  // Not onDestroyed: driver skips it when the tour ends before a step has
  // finished highlighting.
  const finish = () => {
    cancelAnimationFrame(frame)
    if (page === 'conversation') showArtifactTab('facts')
  }
  const tour = driver({
    animate: false,
    overlayOpacity: 0.35,
    overlayClickBehavior: 'none',
    skipMissingElement: true,
    stagePadding: 4,
    stageRadius: 8,
    popoverClass: 'corp-tour-popover',
    showProgress: present.length > 1,
    nextBtnText: 'Next',
    prevBtnText: 'Back',
    doneBtnText: 'Done',
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
        finish()
      })
      popover.footerButtons.prepend(skip)
    },
    // The conversation is the last part, so ending it by Done, the close
    // button or Escape finishes the guide. Tips > Show me around replays it.
    onDestroyStarted: (_element, _step, { driver: active }) => {
      if (page === 'conversation') dismissTour()
      active.destroy()
      finish()
    },
    steps: present.map((id) => toDriveStep(id, built)),
  })
  tour.drive()
  // The home composer moves down once the draft card arrives, and the record
  // pane reflows as facts load. Driver does not notice either, so keep the
  // stage on the active anchor while the tour is open.
  let lastTop = Number.NaN
  let passes = 0
  const watch = () => {
    if (!tour.isActive()) return
    passes += 1
    const top = tour.getActiveElement()?.getBoundingClientRect().top
    const moved = top != null && Math.abs(top - lastTop) > 1
    // The first passes run after the popover has its real height. Measuring
    // before that pins it over the control.
    if (moved || passes <= 4) {
      if (top != null) lastTop = top
      tour.refresh()
    }
    frame = requestAnimationFrame(watch)
  }
  frame = requestAnimationFrame(watch)
  return {
    destroy() {
      tour.destroy()
      finish()
    },
  }
}
