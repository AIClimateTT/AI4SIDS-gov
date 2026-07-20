import * as React from "react"
import { X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { DataTableSearch } from "./data-table-search"
import { DataTableFilterSelect } from "./data-table-filter-select"
import { DataTableFilterFaceted } from "./data-table-filter-faceted"
import { DataTableFilterDate } from "./data-table-filter-date"
import { DataTableViewOptions } from "./data-table-view-options"
import type {
  DataTableToolbarProps,
  SelectFilterConfig,
  FacetedFilterConfig,
  DateFilterConfig,
} from "./types"

/**
 * Data table toolbar with search, filters, and custom actions
 */
export function DataTableToolbar<TData>({
  table,
  filters,
  filterValues = {},
  onStateChange,
  toolbar,
  enableColumnVisibility,
}: DataTableToolbarProps<TData>) {
  // Check if any filters are active
  const hasActiveFilters = React.useMemo(() => {
    if (!filters) return false
    return filters.some((filter) => {
      if (filter.type === "date") {
        const fromKey = `${filter.key}_from`
        const toKey = `${filter.key}_to`
        return (
          filterValues[filter.key] ||
          filterValues[fromKey] ||
          filterValues[toKey]
        )
      }
      if (filter.type === "faceted") {
        const value = filterValues[filter.key]
        return Array.isArray(value) ? value.length > 0 : !!value
      }
      return !!filterValues[filter.key]
    })
  }, [filters, filterValues])

  // Check if search is active
  const searchKey = toolbar?.search?.key
  const searchValue = searchKey ? (filterValues[searchKey] as string) || "" : ""
  const hasActiveSearch = !!searchValue

  // Reset all filters
  const handleResetFilters = () => {
    const resetUpdates: Record<string, undefined> = {}

    // Reset search
    if (searchKey) {
      resetUpdates[searchKey] = undefined
    }

    // Reset all filter values
    filters?.forEach((filter) => {
      resetUpdates[filter.key] = undefined
      if (filter.type === "date") {
        resetUpdates[`${filter.key}_from`] = undefined
        resetUpdates[`${filter.key}_to`] = undefined
      }
    })

    onStateChange({ ...resetUpdates, page: 1 })
  }

  // Handle search change
  const handleSearchChange = (value: string) => {
    onStateChange({ [searchKey!]: value || undefined, page: 1 })
  }

  // Handle filter change
  const handleFilterChange = (key: string, value: any) => {
    onStateChange({ [key]: value, page: 1 })
  }

  // Handle date filter change (may update multiple keys)
  const handleDateFilterChange = (
    updates: Record<string, string | undefined>
  ) => {
    onStateChange({ ...updates, page: 1 })
  }

  // Render individual filter based on type
  const renderFilter = (
    filter: SelectFilterConfig | FacetedFilterConfig | DateFilterConfig
  ) => {
    switch (filter.type) {
      case "select":
        return (
          <DataTableFilterSelect
            key={filter.key}
            filter={filter}
            value={filterValues[filter.key] as string | undefined}
            onChange={(value) => handleFilterChange(filter.key, value)}
          />
        )

      case "faceted":
        return (
          <DataTableFilterFaceted
            key={filter.key}
            filter={filter}
            value={filterValues[filter.key] as string[] | undefined}
            onChange={(value) => handleFilterChange(filter.key, value)}
          />
        )

      case "date":
        return (
          <DataTableFilterDate
            key={filter.key}
            filter={filter}
            values={{
              [filter.key]: filterValues[filter.key] as string | undefined,
              [`${filter.key}_from`]: filterValues[`${filter.key}_from`] as
                | string
                | undefined,
              [`${filter.key}_to`]: filterValues[`${filter.key}_to`] as
                | string
                | undefined,
            }}
            onChange={handleDateFilterChange}
          />
        )

      default:
        return null
    }
  }

  const showToolbar =
    toolbar?.search ||
    (filters && filters.length > 0) ||
    enableColumnVisibility ||
    toolbar?.actions

  if (!showToolbar) return null

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-1 flex-wrap items-center gap-2">
          {/* Search input */}
          {toolbar?.search && (
            <DataTableSearch
              value={searchValue}
              onChange={handleSearchChange}
              placeholder={toolbar.search.placeholder}
              debounceMs={toolbar.search.debounceMs}
            />
          )}

          {/* Filters */}
          {filters?.map((filter) => renderFilter(filter))}

          {/* Reset button */}
          {(hasActiveFilters || hasActiveSearch) && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleResetFilters}
              className="h-9 px-2 lg:px-3"
            >
              Reset
              <X className="ml-2 h-4 w-4" />
            </Button>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* Column visibility */}
          {enableColumnVisibility && <DataTableViewOptions table={table} />}

          {/* Custom actions */}
          {toolbar?.actions}
        </div>
      </div>
    </div>
  )
}
