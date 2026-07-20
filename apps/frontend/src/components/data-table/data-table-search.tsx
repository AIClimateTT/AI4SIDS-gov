import * as React from "react"
import { Search } from "lucide-react"
import { Input } from "@/components/ui/input"
import type { DataTableSearchProps } from "./types"

/**
 * Debounced search input for data table toolbar
 */
export function DataTableSearch({
  value,
  onChange,
  placeholder = "Search...",
  debounceMs = 300,
}: DataTableSearchProps) {
  const [localValue, setLocalValue] = React.useState(value)
  const debounceRef = React.useRef<ReturnType<typeof setTimeout> | null>(null)

  // Sync local value when external value changes (e.g., URL navigation)
  React.useEffect(() => {
    setLocalValue(value)
  }, [value])

  // Cleanup timeout on unmount
  React.useEffect(() => {
    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current)
      }
    }
  }, [])

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = e.target.value
    setLocalValue(newValue)

    // Clear previous timeout
    if (debounceRef.current) {
      clearTimeout(debounceRef.current)
    }

    // Set new debounced update
    debounceRef.current = setTimeout(() => {
      onChange(newValue || "")
    }, debounceMs)
  }

  return (
    <div className="relative">
      <Search className="absolute top-2.5 left-2.5 h-4 w-4 text-muted-foreground" />
      <Input
        placeholder={placeholder}
        value={localValue}
        onChange={handleChange}
        className="h-9 w-[150px] pl-8 lg:w-[250px]"
      />
    </div>
  )
}
