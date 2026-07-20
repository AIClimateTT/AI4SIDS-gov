export type ReportStatus = 'ok' | 'needs_review'

export type TemplateParamInfo = {
  name: string
  required: boolean
}

export type TemplateInfo = {
  name: string
  version: number
  title: string
  description: string
  params: TemplateParamInfo[]
}

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
  fact_table: Record<string, unknown>
  narrative: string
  markdown: string
  status: ReportStatus
  violations: CitationViolation[]
  created_at: string
}

export type GenerateReportInput = {
  template: string
  params: Record<string, string>
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
