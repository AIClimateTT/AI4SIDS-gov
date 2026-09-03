import { Button } from '@/components/ui/button'
import type { DataTableFilterToggleProps } from './types'

/**
 * Exclusive button-group filter. A missing value is treated as `all` so a
 * queue switcher always has one option pressed.
 */
export function DataTableFilterToggle({
  filter,
  value,
  onChange,
}: DataTableFilterToggleProps) {
  const allOption = filter.options.find((option) => option.value === 'all')
  const selected = value ?? allOption?.value

  return (
    <div
      role="group"
      aria-label={filter.label}
      className="flex flex-wrap items-center gap-2"
    >
      {filter.options.map((option) => (
        <Button
          key={option.value}
          size="sm"
          variant={selected === option.value ? 'default' : 'outline'}
          aria-pressed={selected === option.value}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </Button>
      ))}
    </div>
  )
}
