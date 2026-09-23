/**
 * Blank CSV templates downloaded before a file is filled in.
 *
 * Corporation headers must match parse_incident_row / parse_log_row in the
 * backend exactly — a mismatch means a column is silently ignored, which is
 * the failure the row-level error reporting exists to prevent.
 *
 * Survey123 headers are the export shape in
 * apps/backend/fixtures/sample_small.csv. ObjectID and GlobalID are required;
 * a corporation incident template uploaded here is a different file.
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

/** Header row of the Survey123 export that field-data ingest accepts. */
export const SURVEY123_CSV_HEADERS = [
  'ObjectID',
  'GlobalID',
  'CreationDate',
  'Creator',
  'EditDate',
  'Editor',
  'Name of Officer',
  'Position',
  'Organisation',
  'Other - Organisation',
  'Date of Event',
  'Time of Event',
  'Name of Person',
  'Contact Information',
  'Address',
  'Community',
  'Municipal Boundary',
  'Incident Type',
  'Other - Incident Type',
  'Incident Summary',
  'Household Occupants',
  'If more than 6 persons - Household Occupants',
  'Did any injuries occur?',
  'Injuries',
  'Type of Injuries',
  'Did any deaths occur?',
  'Deaths',
  'Building Damage',
  'Crops and Livestock',
  'Personal Items',
  'Furniture and Appliances',
  'Action Taken',
  'Relief Items',
  'Other Agency',
  'Shelter',
  'Are there any special needs occupants?',
  'Please indicate the number of special needs occupants',
  'Estimate Cost of Damage',
  'Identification Card Type',
  'Other - Identification Card Type',
  'Identification Card Number',
  'Follow Up Recommendation',
  'Other - Follow Up Recommendation',
  'Assessment Date',
  'Is the property insured?',
  'Island',
  'District',
  'Ownership',
  'Property Type',
  'Structure Type',
  'Other - Structure Type',
  'Age of Structure (years)',
  'Type of Household',
  'Number of Male Occupants',
  'Number of Female Occupants',
  'What are the age groups of occupants?',
  'Are there any dependents in the household',
  'Number of Dependents',
  'Validated/NotValidated',
  'Please list the names of the occupants and their relation',
  'Employment Status',
  'Employment Sector',
  'Other - Employment Sector',
  'Flood Type',
  'Flood Trigger',
  'Other - Flood Trigger',
  'Flood Height',
  'Other Agency_2',
  'Community_2',
  'Other - Community',
  'Other Agency_3',
  'Other - Other Agency',
  'Name of Second Person',
  'Second Contact Information',
  'Second Identification Card Number',
  'Second Employment Status',
  'x',
  'y',
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
