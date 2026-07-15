"use client"

import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react"

import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"

import { DataTableEmpty } from "./DataTableEmpty"
import { DataTablePagination } from "./DataTablePagination"

interface Column<T> {
  key: string
  header: string
  render: (item: T) => React.ReactNode
  sortable?: boolean
  width?: string
}

interface DataTableProps<T> {
  data: T[]
  columns: Column<T>[]
  total: number
  page: number
  pageSize: number
  onPageChange: (page: number) => void
  onPageSizeChange: (size: number) => void
  loading: boolean
  emptyMessage?: string
  sortKey?: string
  sortDir?: "asc" | "desc"
  onSort?: (key: string, dir: "asc" | "desc") => void
  className?: string
}

const SKELETON_ROWS = 5

function DataTable<T>({
  data,
  columns,
  total,
  page,
  pageSize,
  onPageChange,
  onPageSizeChange,
  loading,
  emptyMessage,
  sortKey,
  sortDir,
  onSort,
  className,
}: DataTableProps<T>) {
  const handleSort = (key: string) => {
    if (!onSort) return
    if (sortKey === key) {
      onSort(key, sortDir === "asc" ? "desc" : "asc")
    } else {
      onSort(key, "asc")
    }
  }

  const renderSortIcon = (key: string) => {
    if (sortKey !== key) {
      return <ArrowUpDown className="size-3.5 text-muted-foreground/40" />
    }
    return sortDir === "asc" ? (
      <ArrowUp className="size-3.5 text-foreground" />
    ) : (
      <ArrowDown className="size-3.5 text-foreground" />
    )
  }

  return (
    <div
      data-slot="data-table"
      className={cn("flex flex-col rounded-lg border border-border", className)}
    >
      <div className="overflow-x-auto">
        <table className="w-full caption-bottom text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/50">
              {columns.map((col) => (
                <th
                  key={col.key}
                  scope="col"
                  className={cn(
                    "h-10 px-3 text-left align-middle text-xs font-medium text-muted-foreground",
                    col.sortable && "cursor-pointer select-none transition-colors hover:text-foreground",
                  )}
                  style={col.width ? { width: col.width } : undefined}
                  onClick={() => col.sortable && handleSort(col.key)}
                  aria-sort={
                    sortKey === col.key
                      ? sortDir === "asc"
                        ? "ascending"
                        : "descending"
                      : undefined
                  }
                >
                  <div className="flex items-center gap-1.5">
                    <span>{col.header}</span>
                    {col.sortable && renderSortIcon(col.key)}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              Array.from({ length: SKELETON_ROWS }).map((_, i) => (
                <tr key={`skeleton-${i}`} className="border-b border-border/50">
                  {columns.map((col) => (
                    <td
                      key={col.key}
                      className="px-3 py-2.5"
                      style={col.width ? { width: col.width } : undefined}
                    >
                      <Skeleton className="h-4 w-full max-w-[120px]" />
                    </td>
                  ))}
                </tr>
              ))
            ) : data.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="p-0">
                  <DataTableEmpty message={emptyMessage} />
                </td>
              </tr>
            ) : (
              data.map((item, rowIndex) => (
                <tr
                  key={rowIndex}
                  className="border-b border-border/50 transition-colors hover:bg-muted/30"
                >
                  {columns.map((col) => (
                    <td
                      key={col.key}
                      className="px-3 py-2.5 align-middle text-foreground"
                      style={col.width ? { width: col.width } : undefined}
                    >
                      {col.render(item)}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {!loading && data.length > 0 && (
        <DataTablePagination
          total={total}
          page={page}
          pageSize={pageSize}
          onPageChange={onPageChange}
          onPageSizeChange={onPageSizeChange}
        />
      )}
    </div>
  )
}

export { DataTable }
export type { Column, DataTableProps }
