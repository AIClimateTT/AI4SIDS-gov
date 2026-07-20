import type {
  IngestResult,
  ModuleInfo,
  OverviewSummary,
  ReportDetail,
  ReportListItem,
  TemplateInfo,
} from '@/types/dmcu'

const SHARED_PARAMS_SCHEMA = {
  type: 'object',
  properties: {
    corporation: { type: 'string' },
    community: { type: 'string' },
    date_from: { type: 'string', format: 'date' },
    date_to: { type: 'string', format: 'date' },
    include_pending: { type: 'boolean', default: false },
  },
}

export const mockTemplates: TemplateInfo[] = [
  {
    name: 'minister_regional_comparison',
    version: 1,
    title: 'Ministerial Regional Comparison Briefing',
    description:
      'One-page briefing comparing incident activity across corporations for a date window.',
    params: [
      { name: 'date_from', required: true },
      { name: 'date_to', required: true },
    ],
  },
  {
    name: 'single_region_report',
    version: 1,
    title: 'Single Region Report',
    description:
      'Focused corporation report with street-level tally, relief actions, and coverage gaps.',
    params: [
      { name: 'corporation', required: true },
      { name: 'date_from', required: true },
      { name: 'date_to', required: true },
    ],
  },
]

export const mockModules: ModuleInfo[] = [
  {
    name: 'survey123',
    metrics: [
      {
        name: 'incident_count',
        description: 'Total incidents, breakdown by incident_type.',
        params_schema: SHARED_PARAMS_SCHEMA,
        module: 'survey123',
      },
      {
        name: 'incidents_by_corporation',
        description: 'Counts per corporation.',
        params_schema: SHARED_PARAMS_SCHEMA,
        module: 'survey123',
      },
      {
        name: 'data_coverage',
        description: 'Validated vs pending coverage.',
        params_schema: SHARED_PARAMS_SCHEMA,
        module: 'survey123',
      },
    ],
  },
  {
    name: 'sitreps',
    metrics: [
      {
        name: 'incident_count',
        description: 'SITREP incidents in the date window.',
        params_schema: SHARED_PARAMS_SCHEMA,
        module: 'sitreps',
      },
      {
        name: 'data_coverage',
        description: 'SITREP validation coverage.',
        params_schema: SHARED_PARAMS_SCHEMA,
        module: 'sitreps',
      },
    ],
  },
]

export const mockReportList: ReportListItem[] = [
  {
    id: 'rpt_7f3a2c1b',
    template: 'minister_regional_comparison',
    template_version: 1,
    params: { date_from: '2025-05-01', date_to: '2025-05-18' },
    status: 'ok',
    created_at: '2025-05-18T16:42:00Z',
  },
  {
    id: 'rpt_91bd44e0',
    template: 'single_region_report',
    template_version: 1,
    params: {
      corporation: 'Diego Martin',
      date_from: '2025-05-10',
      date_to: '2025-05-18',
    },
    status: 'needs_review',
    created_at: '2025-05-18T14:05:00Z',
  },
  {
    id: 'rpt_c2aa8891',
    template: 'single_region_report',
    template_version: 1,
    params: {
      corporation: 'Tunapuna/Piarco',
      date_from: '2025-05-01',
      date_to: '2025-05-18',
    },
    status: 'ok',
    created_at: '2025-05-17T11:20:00Z',
  },
]

export const mockReportDetails: Record<string, ReportDetail> = {
  rpt_7f3a2c1b: {
    id: 'rpt_7f3a2c1b',
    template: 'minister_regional_comparison',
    template_version: 1,
    params: { date_from: '2025-05-01', date_to: '2025-05-18' },
    status: 'ok',
    created_at: '2025-05-18T16:42:00Z',
    narrative:
      'Regional comparison for 1–18 May 2025. Diego Martin led activity with 42 validated incidents [C001].',
    markdown: `# Ministerial Regional Comparison

**Period:** 2025-05-01 to 2025-05-18

Diego Martin recorded the highest validated incident count at **42** [C001].
`,
    fact_table: {
      facts: [
        {
          id: 'C001',
          label: 'Diego Martin incidents',
          value: 42,
          source: 'survey123.incidents_by_corporation',
        },
      ],
    },
    violations: [],
  },
  rpt_91bd44e0: {
    id: 'rpt_91bd44e0',
    template: 'single_region_report',
    template_version: 1,
    params: {
      corporation: 'Diego Martin',
      date_from: '2025-05-10',
      date_to: '2025-05-18',
    },
    status: 'needs_review',
    created_at: '2025-05-18T14:05:00Z',
    narrative:
      'Diego Martin single-region draft. Citation check failed on one figure.',
    markdown: `# Diego Martin Region Report

Draft narrative with an unverified total of **55** incidents.
`,
    fact_table: {
      facts: [
        {
          id: 'C001',
          label: 'Incident count',
          value: 42,
          source: 'survey123.incident_count',
        },
      ],
    },
    violations: [
      {
        kind: 'invented_number',
        detail: 'Narrative cites 55 but FactTable C001 value is 42',
        sentence: 'Draft narrative with an unverified total of 55 incidents.',
        token: '55',
      },
      {
        kind: 'missing_citation',
        detail: 'Missing citation marker on relief sentence',
        sentence: 'Relief was distributed.',
        token: null,
      },
    ],
  },
  rpt_c2aa8891: {
    id: 'rpt_c2aa8891',
    template: 'single_region_report',
    template_version: 1,
    params: {
      corporation: 'Tunapuna/Piarco',
      date_from: '2025-05-01',
      date_to: '2025-05-18',
    },
    status: 'ok',
    created_at: '2025-05-17T11:20:00Z',
    narrative: 'Tunapuna/Piarco region summary for early May.',
    markdown: `# Tunapuna/Piarco Region Report

**28** validated incidents [C001].
`,
    fact_table: {
      facts: [
        {
          id: 'C001',
          label: 'Incident count',
          value: 28,
          source: 'survey123.incident_count',
        },
      ],
    },
    violations: [],
  },
}

export const mockOverview: OverviewSummary = {
  incident_count_survey123: 186,
  incident_count_sitreps: 54,
  report_count: mockReportList.length,
  needs_review_count: mockReportList.filter((r) => r.status === 'needs_review')
    .length,
  recent_reports: mockReportList.slice(0, 5),
}

export const mockIngestResult: IngestResult = {
  rows_read: 120,
  rows_inserted: 112,
  rows_updated: 5,
  duplicates_flagged: 3,
  unmapped_values: {},
  pii_columns_dropped: ['Name of Person'],
}
