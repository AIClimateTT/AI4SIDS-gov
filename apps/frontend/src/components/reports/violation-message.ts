/** A citation problem in words an officer can act on. Never the raw code. */
export function violationMessage(kind: string, token?: string | null): string {
  switch (kind) {
    case 'invented_number':
      return `The figure ${token ?? ''} doesn't match any source.`.replace('  ', ' ')
    case 'missing_citation':
      return 'This sentence has a figure with no source.'
    case 'misattributed_number':
      return `The figure ${token ?? ''} belongs to a different source.`.replace('  ', ' ')
    case 'empty_narrative':
      return 'The report cites no sources.'
    default:
      return 'This sentence needs checking.'
  }
}
