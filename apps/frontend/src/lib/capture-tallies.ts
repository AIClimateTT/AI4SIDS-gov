import type { CaptureIncident } from '@/types/dmcu'

export type WorkingSetTallies = {
  incidents: number
  injuries: number
  deaths: number
  unknownCasualties: number
  reliefSupplied: number
  furtherAssessment: number
}

/** Same predicate as app/modules/capture/missing.py casualties_unknown. */
export function casualtiesUnknown(incident: CaptureIncident): boolean {
  return (
    incident.injuries_count === null &&
    incident.injuries_occurred === null &&
    incident.deaths_count === null &&
    incident.deaths_occurred === null
  )
}

export function workingSetTallies(incidents: CaptureIncident[]): WorkingSetTallies {
  return {
    incidents: incidents.length,
    injuries: incidents.reduce((sum, row) => sum + (row.injuries_count ?? 0), 0),
    deaths: incidents.reduce((sum, row) => sum + (row.deaths_count ?? 0), 0),
    unknownCasualties: incidents.filter(casualtiesUnknown).length,
    reliefSupplied: incidents.filter((row) => row.relief_supplied === true).length,
    furtherAssessment: incidents.filter((row) => row.further_assessment_required === true)
      .length,
  }
}
