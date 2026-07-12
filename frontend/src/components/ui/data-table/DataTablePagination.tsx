"use client"

import { ChevronLeft, ChevronRight } from "lucide-react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

interface DataTablePaginationProps {
  total: number
  page: number
  pageSize: number
  onPageChange: (page: number) => void
  onPageSizeChange: (size: number) => void
  className?: string
}

function DataTablePagination({
  total,
  page,
  pageSize,
  onPageChange,
  onPageSizeChange,
  className,
}: DataTablePaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const start = total === 0 ? 0 : (page - 1) * pageSize + 1
  const end = Math.min(page * pageSize, total)

  return (
    <div
      data-slot="data-table-pagination"
      className={cn(
        "flex items-center justify-between gap-4 border-t border-border px-3 py-2.5 text-sm",
        className
      )}
    >
      <div className="flex items-center gap-2 text-muted-foreground">
        <span className="whitespace-nowrap text-xs">
          Showing{" "}
          <span className="font-medium text-foreground">{start}</span>{" "}
          to{" "}
          <span className="font-medium text-foreground">{end}</span>{" "}
          of{" "}
          <span className="font-medium text-foreground">{total}</span>{" "}
          results
        </span>
      </div>

      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5">
          <label
            htmlFor="data-table-page-size"
            className="whitespace-nowrap text-xs text-muted-foreground"
          >
            Rows per page:
          </label>
          <select
            id="data-table-page-size"
            value={pageSize}
            onChange={(e) => onPageSizeChange(Number(e.target.value))}
            className="h-7 rounded-md border border-input bg-muted px-2 text-xs text-foreground outline-none transition-colors focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30"
          >
            {[10, 20, 50].map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon-xs"
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
            aria-label="Previous page"
          >
            <ChevronLeft className="size-3.5" />
          </Button>

          <span className="min-w-[4rem] text-center text-xs tabular-nums text-muted-foreground">
            Page {page} of {totalPages}
          </span>

          <Button
            variant="ghost"
            size="icon-xs"
            disabled={page >= totalPages}
            onClick={() => onPageChange(page + 1)}
            aria-label="Next page"
          >
            <ChevronRight className="size-3.5" />
          </Button>
        </div>
      </div>
    </div>
  )
}

export { DataTablePagination }
