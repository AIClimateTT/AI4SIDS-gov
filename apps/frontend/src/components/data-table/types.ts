import type { ColumnDef } from '@tanstack/react-table'
import type { LucideIcon } from 'lucide-react'

/**
 * Main DataTable component props
 */
export interface DataTableProps<TData> {
  /** Column definitions for the table */
  columns: ColumnDef<TData, any>[]
  /** Data array to display */
  data: TData[]
  /** Total count for pagination (from server) */
  total: number
  /** Current pagination state */
  pagination: {
    pageIndex: number
    pageSize: number
  }
  /** Callback to update table state (pagination, filters, sorting) */
  onStateChange: (updates: Record<string, any>) => void

  /** Loading state */
  isLoading?: boolean
  /** Error state */
  error?: Error | null

  /** Optional feature flags */
  features?: DataTableFeatures
  /** Filter configurations */
  filters?: FilterConfig[]
  /** Current filter values from URL */
  filterValues?: Record<string, any>
  /** Current sorting state */
  sorting?: SortingState
  /** Toolbar configuration */
  toolbar?: ToolbarConfig
  /** Row actions renderer */
  rowActions?: (row: TData) => React.ReactNode
}

/**
 * Feature flags to enable/disable table features
 */
export interface DataTableFeatures {
  /** Enable column sorting (server-side) */
  enableSorting?: boolean
  /** Enable column visibility toggle */
  enableColumnVisibility?: boolean
  /** Enable page size selector */
  enablePageSizeSelector?: boolean
  /** Available page size options */
  pageSizeOptions?: number[]
}

/**
 * Sorting state from URL
 */
export interface SortingState {
  sortBy?: string
  sortOrder?: 'asc' | 'desc'
}

/**
 * Toolbar configuration
 */
export interface ToolbarConfig {
  /** Search input configuration */
  search?: {
    /** URL param key for search (e.g., 'q') */
    key: string
    /** Placeholder text */
    placeholder?: string
    /** Debounce delay in ms (default: 300) */
    debounceMs?: number
  }
  /** Custom actions to render in toolbar */
  actions?: React.ReactNode
}

/**
 * Filter configuration types
 */
export type FilterConfig =
  | SelectFilterConfig
  | FacetedFilterConfig
  | DateFilterConfig

interface BaseFilterConfig {
  /** URL param key */
  key: string
  /** Display label */
  label: string
}

/**
 * Simple select dropdown filter
 */
export interface SelectFilterConfig extends BaseFilterConfig {
  type: 'select'
  options: Array<{ label: string; value: string }>
}

/**
 * Multi-select faceted filter
 */
export interface FacetedFilterConfig extends BaseFilterConfig {
  type: 'faceted'
  options: Array<{
    label: string
    value: string
    icon?: LucideIcon
  }>
}

/**
 * Date filter with single/range mode toggle
 */
export interface DateFilterConfig extends BaseFilterConfig {
  type: 'date'
  /** Allow switching between single and range mode (default: true) */
  allowRange?: boolean
  /** Default mode (default: 'single') */
  defaultMode?: 'single' | 'range'
}

/**
 * Props for DataTableToolbar
 */
export interface DataTableToolbarProps<TData> {
  table: import('@tanstack/react-table').Table<TData>
  filters?: FilterConfig[]
  filterValues?: Record<string, any>
  onStateChange: (updates: Record<string, any>) => void
  toolbar?: ToolbarConfig
  enableColumnVisibility?: boolean
}

/**
 * Props for DataTablePagination
 */
export interface DataTablePaginationProps {
  pageIndex: number
  pageSize: number
  total: number
  onStateChange: (updates: Record<string, any>) => void
  enablePageSizeSelector?: boolean
  pageSizeOptions?: number[]
}

/**
 * Props for DataTableColumnHeader
 */
export interface DataTableColumnHeaderProps<TData, TValue>
  extends React.HTMLAttributes<HTMLDivElement> {
  column: import('@tanstack/react-table').Column<TData, TValue>
  title: string
  sorting?: SortingState
  onStateChange?: (updates: Record<string, any>) => void
  enableSorting?: boolean
}

/**
 * Props for DataTableSearch
 */
export interface DataTableSearchProps {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  debounceMs?: number
}

/**
 * Props for DataTableFilterSelect
 */
export interface DataTableFilterSelectProps {
  filter: SelectFilterConfig
  value: string | undefined
  onChange: (value: string | undefined) => void
}

/**
 * Props for DataTableFilterFaceted
 */
export interface DataTableFilterFacetedProps {
  filter: FacetedFilterConfig
  value: string[] | undefined
  onChange: (value: string[] | undefined) => void
}

/**
 * Props for DataTableFilterDate
 */
export interface DataTableFilterDateProps {
  filter: DateFilterConfig
  /** Current values - for single mode uses 'key', for range uses 'key_from' and 'key_to' */
  values: Record<string, string | undefined>
  onChange: (updates: Record<string, string | undefined>) => void
}

/**
 * Props for DataTableViewOptions
 */
export interface DataTableViewOptionsProps<TData> {
  table: import('@tanstack/react-table').Table<TData>
}
