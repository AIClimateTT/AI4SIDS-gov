import type { CaptureIncident, CaptureLog } from '@/types/dmcu'

export const ALERT_LEVELS = [
  'green',
  'yellow',
  'orange',
  'red',
  'discontinued',
  'none',
] as const

export const INCIDENT_TYPE_OPTIONS = [
  { value: 'flooding', label: 'Flooding' },
  { value: 'blown off roof', label: 'Blown off roof' },
  { value: 'fallen tree', label: 'Fallen tree' },
  { value: 'landslide', label: 'Landslide' },
  { value: 'fire', label: 'Fire' },
  { value: 'other', label: 'Other' },
] as const

export const LOG_CATEGORY_OPTIONS = [
  { value: 'resource', label: 'Resource' },
  { value: 'personnel', label: 'Personnel' },
  { value: 'facility', label: 'Facility' },
  { value: 'activity', label: 'Activity' },
  { value: 'relief_distributed', label: 'Relief distributed' },
  { value: 'other', label: 'Other' },
] as const

export const LOG_STATUS_OPTIONS = [
  { value: 'none', label: 'Not set' },
  { value: 'available', label: 'Available' },
  { value: 'prepositioned', label: 'Prepositioned' },
  { value: 'in_stock', label: 'In stock' },
  { value: 'inspected', label: 'Inspected' },
  { value: 'on_standby', label: 'On standby' },
  { value: 'ongoing', label: 'Ongoing' },
  { value: 'completed', label: 'Completed' },
  { value: 'procuring', label: 'Procuring' },
] as const

export type IncidentFormValues = {
  community: string
  street: string
  incident_type: string
  incident_summary: string
  event_date: string
  injuries_count: string
  deaths_count: string
}

export type LogFormValues = {
  category: string
  statement: string
  item: string
  quantity: string
  unit: string
  status: string
}

export function nextIncidentRowId(incidents: { row_id: string }[]): string {
  const nums = incidents
    .map((item) => Number.parseInt(item.row_id, 10))
    .filter((value) => Number.isFinite(value) && value > 0)
  return String((nums.length > 0 ? Math.max(...nums) : 0) + 1)
}

export function nextLogRowId(logs: { row_id: string }[]): string {
  const nums = logs
    .map((item) => Number.parseInt(item.row_id, 10))
    .filter((value) => Number.isFinite(value) && value > 0)
  return String((nums.length > 0 ? Math.max(...nums) : 0) + 1)
}

export function parseOptionalNumber(raw: string): number | null {
  const trimmed = raw.trim()
  if (!trimmed) return null
  const value = Number(trimmed)
  return Number.isFinite(value) ? value : null
}

export function casualtyOccurred(count: number | null): boolean | null {
  if (count === null) return null
  return count > 0
}

export function formToCaptureIncident(
  form: IncidentFormValues,
  rowId: string,
): CaptureIncident {
  const injuriesCount = parseOptionalNumber(form.injuries_count)
  const deathsCount = parseOptionalNumber(form.deaths_count)
  return {
    row_id: rowId,
    community: form.community.trim() || null,
    street: form.street.trim() || null,
    incident_type: form.incident_type.trim() || null,
    raw_incident_type: null,
    incident_summary: form.incident_summary.trim() || null,
    event_date: form.event_date.trim() || null,
    injuries_occurred: casualtyOccurred(injuriesCount),
    injuries_count: injuriesCount,
    deaths_occurred: casualtyOccurred(deathsCount),
    deaths_count: deathsCount,
    building_damage: null,
    special_needs_occupants: null,
    estimated_damage_cost: null,
    action_taken: null,
    relief_supplied: null,
    forwarded_to_agency: null,
    further_assessment_required: null,
    other_follow_up: null,
  }
}

export function formToCaptureLog(form: LogFormValues, rowId: string): CaptureLog {
  return {
    row_id: rowId,
    category: form.category.trim() || 'other',
    statement: form.statement.trim(),
    item: form.item.trim() || null,
    quantity: parseOptionalNumber(form.quantity),
    unit: form.unit.trim() || null,
    status: form.status.trim() && form.status !== 'none' ? form.status.trim() : null,
  }
}

export function toDatetimeLocal(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso.slice(0, 16)
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}`
}

export function toIsoDateTime(value: string): string {
  return value.length === 16 ? `${value}:00` : value
}
