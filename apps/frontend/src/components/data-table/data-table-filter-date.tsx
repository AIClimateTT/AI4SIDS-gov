import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import type { DateFilterConfig } from './types'

interface DataTableFilterDateProps {
  filter: DateFilterConfig
  values: Record<string, string | undefined>
  onChange: (updates: Record<string, string | undefined>) => void
}

/**
 * Date filter with from/to native date inputs.
 * Uses filter.key_from / filter.key_to for range queries.
 */
export function DataTableFilterDate({
  filter,
  values,
  onChange,
}: DataTableFilterDateProps) {
  const fromKey = `${filter.key}_from`
  const toKey = `${filter.key}_to`

  return (
    <div className="flex flex-wrap items-end gap-2">
      <div className="space-y-1">
        <Label htmlFor={fromKey} className="text-xs text-muted-foreground">
          {filter.label} from
        </Label>
        <Input
          id={fromKey}
          type="date"
          className="h-9 w-[150px]"
          value={values[fromKey] ?? ''}
          onChange={(event) =>
            onChange({
              [fromKey]: event.target.value || undefined,
              [filter.key]: undefined,
            })
          }
        />
      </div>
      <div className="space-y-1">
        <Label htmlFor={toKey} className="text-xs text-muted-foreground">
          {filter.label} to
        </Label>
        <Input
          id={toKey}
          type="date"
          className="h-9 w-[150px]"
          value={values[toKey] ?? ''}
          onChange={(event) =>
            onChange({
              [toKey]: event.target.value || undefined,
              [filter.key]: undefined,
            })
          }
        />
      </div>
    </div>
  )
}
