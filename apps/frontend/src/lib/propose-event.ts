import type { CaptureIncident, CaptureSession } from '@/types/dmcu'

export const EVENT_HAZARD_TYPES = [
  'flood',
  'landslide',
  'wind',
  'fire',
  'other',
] as const

export type EventHazardType = (typeof EVENT_HAZARD_TYPES)[number]

export type ProposedEvent = {
  title: string
  hazard_type: EventHazardType
  started_at: string
}

const TYPE_TO_HAZARD: Record<string, EventHazardType> = {
  flooding: 'flood',
  flooding_: 'flood',
  landslide: 'landslide',
  fire: 'fire',
  blown_off_roof: 'wind',
  'blown off roof': 'wind',
  fallen_tree: 'wind',
  wind: 'wind',
}

function firstSentence(text: string): string {
  const trimmed = text.trim()
  const match = trimmed.match(/^(.+?)(?:[.!?](?:\s|$)|$)/)
  return (match?.[1] ?? trimmed).trim()
}

function placeTitle(incident: CaptureIncident): string | null {
  const street = incident.street?.trim()
  const community = incident.community?.trim()
  if (street && community) return `${street}, ${community}`
  return street || community || null
}

function datePart(value: string | null | undefined): string | null {
  if (!value) return null
  const match = value.match(/^(\d{4}-\d{2}-\d{2})/)
  return match?.[1] ?? null
}

function hazardFromType(incidentType: string | null): EventHazardType {
  if (!incidentType) return 'other'
  return TYPE_TO_HAZARD[incidentType.trim().toLowerCase()] ?? 'other'
}

export function proposeEventFromSession(session: CaptureSession): ProposedEvent {
  const first = session.incidents[0]
  const overview = session.situation_overview?.trim()
  const summary = first?.incident_summary?.trim()
  const place = first ? placeTitle(first) : null
  const alert =
    session.alert_level && session.alert_level !== 'none'
      ? `${session.alert_level.charAt(0).toUpperCase()}${session.alert_level.slice(1)} alert`
      : null

  return {
    title: overview
      ? firstSentence(overview)
      : summary || place || alert || 'Untitled event',
    hazard_type: hazardFromType(first?.incident_type ?? null),
    started_at:
      datePart(first?.event_date) || datePart(session.as_at) || '1970-01-01',
  }
}
