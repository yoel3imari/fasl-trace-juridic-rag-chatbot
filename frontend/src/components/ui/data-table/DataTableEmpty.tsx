"use client"

import { FileSearch } from "lucide-react"

import { cn } from "@/lib/utils"

interface DataTableEmptyProps {
  message?: string
  className?: string
}

function DataTableEmpty({ message = "No results found.", className }: DataTableEmptyProps) {
  return (
    <div
      data-slot="data-table-empty"
      className={cn(
        "flex flex-col items-center justify-center px-4 py-16 text-center gap-3",
        className
      )}
    >
      <div className="flex items-center justify-center rounded-full bg-muted p-3">
        <FileSearch className="size-6 text-muted-foreground" />
      </div>
      <p className="max-w-xs text-sm text-muted-foreground">{message}</p>
    </div>
  )
}

export { DataTableEmpty }
