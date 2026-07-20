import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { DataTableFilterSelectProps } from "./types"

/**
 * Simple select dropdown filter
 */
export function DataTableFilterSelect({
  filter,
  value,
  onChange,
}: DataTableFilterSelectProps) {
  return (
    <Select
      value={value || ""}
      onValueChange={(val) => onChange(val || undefined)}
    >
      <SelectTrigger className="h-9 w-[150px]">
        <SelectValue placeholder={filter.label} />
      </SelectTrigger>
      <SelectContent>
        {filter.options.map((option) => (
          <SelectItem key={option.value} value={option.value}>
            {option.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
