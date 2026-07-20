import * as React from "react"
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type VisibilityState,
} from "@tanstack/react-table"
import { AlertCircle } from "lucide-react"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { DataTableToolbar } from "./data-table-toolbar"
import { DataTablePagination } from "./data-table-pagination"
import type { DataTableProps } from "./types"
import { Skeleton } from "@/components/ui/skeleton"

/**
 * Reusable server-driven data table with optional features
 *
 * Features (all optional):
 * - Server-side pagination via URL state
 * - Server-side sorting via URL state
 * - Decoupled filters (select, faceted, date range)
 * - Column visibility toggle
 * - Page size selector
 * - Debounced search
 * - Custom toolbar actions
 * - Row actions
 */
export function DataTable<TData>({
  columns: userColumns,
  data,
  total,
  pagination,
  onStateChange,
  isLoading = false,
  error,
  features = {},
  filters,
  filterValues = {},
  sorting: _sorting,
  toolbar,
  rowActions,
}: DataTableProps<TData>) {
  // Column visibility state (client-side only)
  const [columnVisibility, setColumnVisibility] =
    React.useState<VisibilityState>({})

  // Add row actions column if provided
  const columns = React.useMemo(() => {
    if (!rowActions) return userColumns

    return [
      ...userColumns,
      {
        id: "actions",
        cell: ({ row }) => rowActions(row.original),
        enableHiding: false,
      },
    ]
  }, [userColumns, rowActions])

  // Initialize table
  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    manualPagination: true,
    manualSorting: true,
    pageCount: Math.ceil(total / pagination.pageSize),
    state: {
      pagination,
      columnVisibility,
    },
    onColumnVisibilityChange: setColumnVisibility,
    enableHiding: features.enableColumnVisibility,    
  })

  // Error state
  if (error) {
    return (
      <div className="flex items-center justify-center rounded-lg border border-destructive/20 bg-destructive/10 p-8 text-destructive">
        <AlertCircle className="mr-2 h-5 w-5" />
        <span>
          Error loading data: {error.message || "Failed to load data"}
        </span>
      </div>
    )
  }

  return (
    <div className="w-full space-y-4">
      {/* Toolbar */}
      <DataTableToolbar
        table={table}
        filters={filters}
        filterValues={filterValues}
        onStateChange={onStateChange}
        toolbar={toolbar}
        enableColumnVisibility={features.enableColumnVisibility}
      />

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <TableHead key={header.id} colSpan={header.colSpan}>
                    {header.isPlaceholder
                      ? null
                      : flexRender(
                          header.column.columnDef.header,
                          header.getContext()
                        )}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {isLoading ? (
              Array.from({ length: 5 }).map((_, rowIndex) => (
                <TableRow key={`loading-row-${rowIndex}`}>
                  {table.getVisibleLeafColumns().map((column) => (
                    <TableCell key={`loading-cell-${rowIndex}-${column.id}`}>
                      <Skeleton className="h-5 w-full" />
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : table.getRowModel().rows?.length ? (
              table.getRowModel().rows.map((row) => (
                <TableRow
                  key={row.id}
                  data-state={row.getIsSelected() && "selected"}
                >
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext()
                      )}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell
                  colSpan={columns.length}
                  className="h-24 text-center text-muted-foreground"
                >
                  No results found.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      <DataTablePagination
        pageIndex={pagination.pageIndex}
        pageSize={pagination.pageSize}
        total={total}
        onStateChange={onStateChange}
        enablePageSizeSelector={features.enablePageSizeSelector}
        pageSizeOptions={features.pageSizeOptions}
      />
    </div>
  )
}
