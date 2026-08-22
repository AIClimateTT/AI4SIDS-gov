export type ReportStatus = 'ok' | 'needs_review' | 'queued' | 'running' | 'failed'

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
  error?: string | null
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
  error?: string | null
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

export type ProposedIncident = {
  corporation: string | null
  community: string | null
  street: string | null
  incident_type: string | null
  incident_summary: string
  event_date: string | null
  injuries_count: number | null
  deaths_count: number | null
  source_index: number
  source_quote: string
}

export type ProposedLog = {
  corporation: string | null
  category: string
  statement: string
  item: string | null
  quantity: number | null
  unit: string | null
  status: string | null
  source_index: number
  source_quote: string
}

export type DraftIncident = ProposedIncident & { included: boolean }
export type DraftLog = ProposedLog & { included: boolean }

export type WhatsAppDraft = {
  id: number
  draft_id: number
  filename: string
  as_at: string
  message_count: number
  pii_redacted: boolean
  incidents: DraftIncident[]
  logs: DraftLog[]
  status?: string
  error?: string | null
  created_at: string
  updated_at: string
}

export type WhatsAppDraftSummary = {
  id: number
  filename: string
  as_at: string
  updated_at: string
  incident_count: number
  log_count: number
}

export type WhatsAppDraftUpdate = {
  as_at?: string
  incidents: DraftIncident[]
  logs: DraftLog[]
}

export type WhatsAppExtractResult = WhatsAppDraft

export type WhatsAppConfirmInput = {
  as_at: string
  filename: string
  incidents: ProposedIncident[]
  logs: ProposedLog[]
}

export type WhatsAppConfirmResult = {
  submissions: SubmissionIngestResult[]
}

export type WhatsAppBriefingResult = {
  id: string
  status: ReportStatus
  markdown: string
  error?: string | null
}

export type CaptureIncident = {
  row_id: string
  community: string | null
  street: string | null
  incident_type: string | null
  raw_incident_type: string | null
  incident_summary: string | null
  event_date: string | null
  injuries_occurred: boolean | null
  injuries_count: number | null
  deaths_occurred: boolean | null
  deaths_count: number | null
  building_damage: string | null
  special_needs_occupants: number | null
  estimated_damage_cost: number | null
  action_taken: string | null
  relief_supplied: boolean | null
  forwarded_to_agency: boolean | null
  further_assessment_required: boolean | null
  other_follow_up: boolean | null
}

export type CaptureLog = {
  row_id: string
  category: string
  statement: string
  item: string | null
  quantity: number | null
  unit: string | null
  status: string | null
}

export type CaptureMessage = {
  role: string
  content: string
  created_at: string
}

export type CaptureMissingField = {
  path: string
  message: string
}

export type CaptureSitrep = {
  markdown: string
  fact_table: FactTable
  violations: CitationViolation[]
  status: string
  generated_at: string
  source_updated_at: string
  stale: boolean
}

export type CaptureSession = {
  id: number
  corporation: string
  event_id: number | null
  status: 'draft' | 'filed' | string
  as_at: string
  alert_level: string
  present_activity: string | null
  situation_overview: string | null
  incidents: CaptureIncident[]
  logs: CaptureLog[]
  manual_fields: string[]
  messages: CaptureMessage[]
  missing: CaptureMissingField[]
  submission_id: number | null
  report_id: string | null
  sitrep: CaptureSitrep | null
  created_at: string
  updated_at: string
}

export type CaptureSessionUpdate = {
  as_at?: string
  alert_level?: string
  present_activity?: string | null
  situation_overview?: string | null
  incidents: CaptureIncident[]
  logs: CaptureLog[]
  manual_fields: string[]
}

export type AttachEventBody =
  | { event_id: number }
  | { title: string; hazard_type: string; started_at: string }

export type CaptureFileResult = {
  session: CaptureSession
  ingest: SubmissionIngestResult
}

export type CaptureCsvKind = 'incidents' | 'logs'

export type CaptureCsvImportResult = {
  session: CaptureSession
  kind: CaptureCsvKind
  rows_read: number
  rows_accepted: number
  row_errors: Array<{ file: string; row_number: number; reason: string }>
}
