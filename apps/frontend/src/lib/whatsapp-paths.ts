// Mirrors app/modules/whatsapp/provenance.py. The backend is the enforcement
// point; these helpers only build the paths the UI reports as hand-edited.
export function incidentPath(rowId: string, field: string): string {
  return `incident:${rowId}.${field}`
}

export function logPath(rowId: string, field: string): string {
  return `log:${rowId}.${field}`
}

export function withManual(manual: string[], path: string): string[] {
  return manual.includes(path) ? manual : [...manual, path]
}

export function withManualPaths(manual: string[], paths: string[]): string[] {
  return paths.reduce((next, path) => withManual(next, path), manual)
}
