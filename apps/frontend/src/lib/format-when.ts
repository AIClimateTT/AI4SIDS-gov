/**
 * Timestamps in an operations record, formatted so a column of them can be
 * compared at a glance.
 *
 * Every call site used a bare `toLocaleString()`, which renders
 * "6/30/2023, 4:00:00 PM": seconds nobody files to, a 12-hour clock that makes
 * two filings four hours apart look alike, and a month/day order that reads
 * backwards outside the US. What an officer actually does with these is scan a
 * column and compare rows to each other, so the fields need to line up and the
 * day needs to be unambiguous.
 *
 * `as_at` and `updated_at` come off the API naive (no offset), so they are
 * parsed as local time — the same behaviour the bare calls had.
 */
const WHEN: Intl.DateTimeFormatOptions = {
  day: '2-digit',
  month: 'short',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
}

const DAY: Intl.DateTimeFormatOptions = {
  day: '2-digit',
  month: 'short',
  year: 'numeric',
}

/**
 * An em dash rather than an empty string or the raw text: a cell that renders
 * nothing reads as a layout bug, and echoing an unparseable timestamp back at
 * the officer implies it means something.
 */
const UNKNOWN = '—'

function parse(value: string | null | undefined): Date | null {
  if (!value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

/** Day and time, e.g. "30 Jun 2023, 16:00". */
export function formatWhen(value: string | null | undefined): string {
  const date = parse(value)
  return date ? date.toLocaleString(undefined, WHEN) : UNKNOWN
}

/** Day only, e.g. "30 Jun 2023". */
export function formatDay(value: string | null | undefined): string {
  const date = parse(value)
  return date ? date.toLocaleDateString(undefined, DAY) : UNKNOWN
}
