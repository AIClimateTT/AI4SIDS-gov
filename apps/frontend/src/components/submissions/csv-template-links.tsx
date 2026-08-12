import { DownloadIcon } from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  INCIDENT_CSV_HEADERS,
  LOG_CSV_HEADERS,
  downloadCsvTemplate,
} from '@/lib/csv-templates'

/** Blank CSV downloads with the exact headers the ingest parser expects. */
export function CsvTemplateLinks() {
  return (
    <div className="space-y-2">
      <p className="text-sm text-muted-foreground">
        Download a blank template, fill it in, and upload it below.
      </p>
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => downloadCsvTemplate('incidents.csv', INCIDENT_CSV_HEADERS)}
        >
          <DownloadIcon />
          Incidents template
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => downloadCsvTemplate('situation-logs.csv', LOG_CSV_HEADERS)}
        >
          <DownloadIcon />
          Situation logs template
        </Button>
      </div>
    </div>
  )
}
