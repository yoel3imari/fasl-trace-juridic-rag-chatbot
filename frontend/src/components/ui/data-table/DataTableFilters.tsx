"use client"

import { useEffect, useRef, useState } from "react"
import { Search, X } from "lucide-react"

import { cn } from "@/lib/utils"

interface FilterConfig {
  key: string
  label: string
  type: "search" | "select"
  options?: { label: string; value: string }[]
  value: string
  onChange: (key: string, value: string) => void
}

interface DataTableFiltersProps {
  filters: FilterConfig[]
  className?: string
  onClearAll?: () => void
}

function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState(value)

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])

  return debouncedValue
}

function SearchFilter({
  filter,
}: {
  filter: FilterConfig
}) {
  const [localValue, setLocalValue] = useState(filter.value)
  const debouncedValue = useDebounce(localValue, 300)
  const isFirstRender = useRef(true)

  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false
      return
    }
    if (debouncedValue !== filter.value) {
      filter.onChange(filter.key, debouncedValue)
    }
  }, [debouncedValue, filter.key, filter.onChange, filter.value])

  useEffect(() => {
    if (filter.value === "" && localValue !== "") {
      setLocalValue("")
    }
  }, [filter.value, localValue])

  return (
    <div className="relative min-w-[160px] max-w-[260px] flex-1">
      <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
      <input
        type="text"
        placeholder={`Search ${filter.label.toLowerCase()}...`}
        value={localValue}
        onChange={(e) => setLocalValue(e.target.value)}
        className="h-8 w-full rounded-md border border-input bg-muted pl-8 pr-2.5 text-xs text-foreground outline-none transition-colors placeholder:text-muted-foreground/60 focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30"
      />
    </div>
  )
}

function DataTableFilters({ filters, className, onClearAll }: DataTableFiltersProps) {
  const hasActiveFilters = filters.some((f) => f.value !== "")

  const handleClearAll = () => {
    onClearAll?.()
  }

  if (!filters.length) return null

  return (
    <div
      data-slot="data-table-filters"
      className={cn(
        "flex flex-wrap items-center gap-2 border-b border-border px-3 py-2.5",
        className
      )}
    >
      {filters.map((filter) => {
        if (filter.type === "search") {
          return <SearchFilter key={filter.key} filter={filter} />
        }

        if (filter.type === "select") {
          return (
            <div key={filter.key} className="min-w-[140px]">
              <select
                value={filter.value}
                onChange={(e) => filter.onChange(filter.key, e.target.value)}
                className="h-8 w-full rounded-md border border-input bg-muted px-2.5 text-xs text-foreground outline-none transition-colors focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30"
              >
                <option value="">All {filter.label.toLowerCase()}</option>
                {filter.options?.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
          )
        }

        return null
      })}

      {hasActiveFilters && (
        <button
          onClick={handleClearAll}
          className="flex items-center gap-1 whitespace-nowrap text-xs text-muted-foreground transition-colors hover:text-foreground"
        >
          <X className="size-3" />
          Clear filters
        </button>
      )}
    </div>
  )
}

export { DataTableFilters }
export type { FilterConfig }
