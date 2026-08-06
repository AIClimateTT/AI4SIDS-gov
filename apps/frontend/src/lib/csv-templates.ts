/**
 * Blank CSV templates a corporation downloads before filling one in.
 *
 * These header strings must match parse_incident_row / parse_log_row in the
 * backend exactly — a mismatch means a column is silently ignored, which is
 * the failure the row-level error reporting exists to prevent.
 */
export const INCIDENT_CSV_HEADERS = [
  'Row ID', 'Community', 'Street', 'Incident Type', 'Date of Event',
  'Incident Summary', 'Injuries Occurred', 'Injuries Count',
  'Deaths Occurred', 'Deaths Count', 'Building Damage',
  'Special Needs Occupants', 'Estimated Damage Cost', 'Action Taken',
  'Relief Supplied', 'Forwarded To Agency', 'Further Assessment Required',
  'Other Follow Up',
] as const

export const LOG_CSV_HEADERS = [
  'Category', 'Statement', 'Item', 'Quantity', 'Unit', 'Status',
] as const

export function csvTemplateText(headers: readonly string[]): string {
  const escaped = headers.map((h) =>
    h.includes(',') || h.includes('"') ? `"${h.replace(/"/g, '""')}"` : h,
  )
  return `${escaped.join(',')}\n`
}

export function downloadCsvTemplate(filename: string, headers: readonly string[]): void {
  const blob = new Blob([csvTemplateText(headers)], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}
