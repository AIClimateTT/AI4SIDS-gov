export type ReportStatus = 'ok' | 'needs_review'

export type TemplateParamInfo = {
  name: string
  required: boolean
}

export type DataRequirementInfo = {
  module: string
  metric: string
  params: Record<string, string>
}

export type NarrationInfo = {
  system_prompt: string
  output_sections: string[]
}

export type TemplateInfo = {
  name: string
  version: number
  title: string
  description: string
  params: TemplateParamInfo[]
  data_requirements: DataRequirementInfo[]
  narration: NarrationInfo
}

export type TemplateVersionSummary = {
  name: string
  version: number
  title: string
  created_at: string
}

export type CreateTemplateVersionInput = {
  name: string
  title: string
  description: string
  params: TemplateParamInfo[]
  data_requirements: DataRequirementInfo[]
  narration: NarrationInfo
}

export const CITATION_RULES = `RULES (absolute — always apply):
- Use ONLY numbers present in the fact table you are given as JSON. Never compute, sum, estimate, or round a number that is not already present.
- Every sentence containing a figure must end with its citation marker, e.g. [C001]. Citation markers look like C001, C002, etc.
- Distinguish validated vs pending figures exactly as labeled in the fact table's "verification" field.
- If the fact table lists gaps, state them plainly in a Data Gaps section.`

export type MetricSpec = {
  name: string
  description: string
  params_schema: {
    type?: string
    properties?: Record<string, unknown>
    [key: string]: unknown
  }
  module: string
}

export type ModuleInfo = {
  name: string
  metrics: MetricSpec[]
}

export type CitationViolation = {
  kind: string
  detail: string
  sentence?: string
  token?: string | null
}

export type FactCitation = {
  cid: string
  module: string
  description: string
  query_ref: string
  record_ids?: string[] | null
  as_of: string
}

export type Fact = {
  metric: string
  value: number | string
  unit: string | null
  scope: Record<string, string>
  breakdown: Record<string, number | string> | null
  verification: 'validated' | 'pending' | 'mixed' | 'n/a' | string
  citation: FactCitation
  /** Caveats the metric raised about its own rows. Also hoisted into
   * FactTable.gaps, which is what the report's Data Gaps section renders. */
  gaps?: string[]
}

export type FactTable = {
  request_id?: string
  template?: string
  template_version?: number
  params?: Record<string, string>
  generated_at?: string
  facts: Fact[]
  gaps?: string[]
}

export type ReportListItem = {
  id: string
  template: string
  template_version: number
  params: Record<string, string>
  status: ReportStatus
  created_at: string
}

export type ReportDetail = {
  id: string
  template: string
  template_version: number
  params: Record<string, string>
  data_requirements: DataRequirementInfo[]
  fact_table: FactTable
  narrative: string
  markdown: string
  status: ReportStatus
  violations: CitationViolation[]
  created_at: string
}

export type GenerateReportInput = {
  template: string
  params: Record<string, string>
  version?: number
  data_requirements?: DataRequirementInfo[]
}

export type GenerateReportResult = {
  id: string
  status: ReportStatus
  markdown: string
}

export type ReportListParams = {
  page?: number
  pageSize?: number
  q?: string
  status?: ReportStatus | 'all'
  sortBy?: string
  sortOrder?: 'asc' | 'desc'
}

export type ReportListResponse = {
  items: ReportListItem[]
  total: number
}

export type OverviewSummary = {
  incident_count_survey123: number
  incident_count_sitreps: number
  report_count: number
  needs_review_count: number
  recent_reports: ReportListItem[]
}

export type IngestModuleName = 'survey123' | 'sitreps'

export type IngestResult = {
  rows_read: number
  rows_inserted: number
  rows_updated: number
  duplicates_flagged: number
  unmapped_values: Record<string, string[]>
  pii_columns_dropped: string[]
}

export type EventSummary = {
  id: number
  corporation: string
  title: string
  hazard_type: string
  started_at: string
  ended_at: string | null
}

export type CreateEventInput = {
  corporation: string
  title: string
  hazard_type: string
  started_at: string
}

export type RowErrorInfo = {
  file: 'incidents' | 'logs'
  /** Spreadsheet row — the header is row 1. Display as-is; the backend
   *  already offsets it, so adding another would send an officer to the
   *  wrong line. */
  row_number: number
  reason: string
}

export type SubmissionSummary = {
  id: number
  corporation: string
  event_id: number | null
  event_title: string | null
  as_at: string
  alert_level: string
  sequence_no: number
  incident_count: number
  log_count: number
}

export type SubmissionDetail = SubmissionSummary & {
  present_activity: string | null
  situation_overview: string | null
  source_file: string | null
  row_errors: RowErrorInfo[]
}

export type SubmissionIngestResult = {
  submission_id: number
  sequence_no: number
  incidents_read: number
  incidents_inserted: number
  incidents_updated: number
  logs_read: number
  logs_inserted: number
  row_errors: RowErrorInfo[]
  unmapped_values: Record<string, string[]>
  pii_columns_dropped: string[]
}

export type FileSubmissionInput = {
  corporation: string
  as_at: string
  event_id?: number
  alert_level: string
  present_activity?: string
  situation_overview?: string
  incidentsFile?: File
  logsFile?: File
}
