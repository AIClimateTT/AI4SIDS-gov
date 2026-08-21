// Mirrors app/modules/capture/provenance.py. The backend is the enforcement
// point; these helpers only build the paths the UI reports as hand-edited.
export const SESSION_FIELDS = [
  'as_at',
  'alert_level',
  'present_activity',
  'situation_overview',
] as const

export function incidentPath(rowId: string, field: string): string {
  return `incident:${rowId}.${field}`
}

export function logPath(rowId: string, field: string): string {
  return `log:${rowId}.${field}`
}

export function withManual(manual: string[], path: string): string[] {
  return manual.includes(path) ? manual : [...manual, path]
}
