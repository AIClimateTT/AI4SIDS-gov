// Main component
export { DataTable } from './data-table'

// Sub-components (for custom composition if needed)
export { DataTableToolbar } from './data-table-toolbar'
export { DataTablePagination } from './data-table-pagination'
export { DataTableColumnHeader } from './data-table-column-header'
export { DataTableSearch } from './data-table-search'
export { DataTableFilterSelect } from './data-table-filter-select'
export { DataTableFilterFaceted } from './data-table-filter-faceted'
export { DataTableFilterDate } from './data-table-filter-date'
export { DataTableFilterToggle } from './data-table-filter-toggle'
export { DataTableViewOptions } from './data-table-view-options'

// // Hooks
// export { useDataTable } from './useDataTable'
// export { useTableState } from './useTableState'

// Types
export type {
  DataTableProps,
  DataTableFeatures,
  SortingState,
  ToolbarConfig,
  FilterConfig,
  SelectFilterConfig,
  FacetedFilterConfig,
  DateFilterConfig,
  ToggleFilterConfig,
  DataTableToolbarProps,
  DataTablePaginationProps,
  DataTableColumnHeaderProps,
  DataTableSearchProps,
  DataTableFilterSelectProps,
  DataTableFilterFacetedProps,
  DataTableFilterDateProps,
  DataTableFilterToggleProps,
  DataTableViewOptionsProps,
} from './types'

// export type { UseDataTableOptions } from './hooks/useDataTable'
// export type { UseTableStateOptions, TableState } from './hooks/useTableState'
