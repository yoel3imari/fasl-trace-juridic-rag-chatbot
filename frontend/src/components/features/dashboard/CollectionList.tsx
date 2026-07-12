"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { Plus, Trash2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { DataTable } from "@/components/ui/data-table/DataTable"
import type { Column } from "@/components/ui/data-table/DataTable"
import { DataTableFilters } from "@/components/ui/data-table/DataTableFilters"
import type { FilterConfig } from "@/components/ui/data-table/DataTableFilters"
import { api, type CollectionResponse } from "@/lib/data"

import { CollectionCreateDialog } from "./CollectionCreateDialog"
import { CollectionDeleteDialog } from "./CollectionDeleteDialog"

export function CollectionList() {
  const [collections, setCollections] = useState<CollectionResponse[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [search, setSearch] = useState("")
  const [sortKey, setSortKey] = useState<string | undefined>("created")
  const [sortDir, setSortDir] = useState<"asc" | "desc" | undefined>("desc")

  const [createOpen, setCreateOpen] = useState(false)
  const [deleteCollection, setDeleteCollection] = useState<{
    id: string
    name: string
  } | null>(null)

  const fetchCollections = useCallback(async () => {
    setLoading(true)
    try {
      const skip = (page - 1) * pageSize
      const result = await api.listCollections({ skip, limit: pageSize, search: search || undefined })
      setCollections(result.collections)
      setTotal(result.total)
    } finally {
      setLoading(false)
    }
  }, [page, pageSize, search])

  useEffect(() => {
    fetchCollections()
  }, [fetchCollections])

  const handleSearchChange = useCallback(
    (_key: string, value: string) => {
      setSearch(value)
      setPage(1)
    },
    [],
  )

  const handleClearFilters = useCallback(() => {
    setSearch("")
    setPage(1)
  }, [])

  const handleSort = useCallback((key: string, dir: "asc" | "desc") => {
    setSortKey(key)
    setSortDir(dir)
  }, [])

  const sortedCollections = useMemo(() => {
    if (!sortKey || !sortDir) return collections
    return [...collections].sort((a, b) => {
      let aVal: string | number = ""
      let bVal: string | number = ""

      if (sortKey === "name") {
        aVal = a.name.toLowerCase()
        bVal = b.name.toLowerCase()
      } else if (sortKey === "created") {
        aVal = new Date(a.created_at).getTime()
        bVal = new Date(b.created_at).getTime()
      }

      if (aVal < bVal) return sortDir === "asc" ? -1 : 1
      if (aVal > bVal) return sortDir === "asc" ? 1 : -1
      return 0
    })
  }, [collections, sortKey, sortDir])

  const filters: FilterConfig[] = useMemo(
    () => [
      {
        key: "search",
        label: "Name",
        type: "search",
        value: search,
        onChange: handleSearchChange,
      },
    ],
    [search, handleSearchChange],
  )

  const columns: Column<CollectionResponse>[] = useMemo(
    () => [
      {
        key: "name",
        header: "Name",
        sortable: true,
        render: (item) => (
          <span className="font-medium text-foreground">{item.name}</span>
        ),
      },
      {
        key: "documents",
        header: "Documents",
        width: "120px",
        render: () => (
          <span className="text-muted-foreground">&mdash;</span>
        ),
      },
      {
        key: "created",
        header: "Created",
        sortable: true,
        width: "160px",
        render: (item) => (
          <span className="text-muted-foreground">
            {new Date(item.created_at).toLocaleDateString(undefined, {
              year: "numeric",
              month: "short",
              day: "numeric",
            })}
          </span>
        ),
      },
      {
        key: "actions",
        header: "",
        width: "48px",
        render: (item) => (
          <button
            type="button"
            onClick={() => setDeleteCollection({ id: item.id, name: item.name })}
            className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
            aria-label={`Delete ${item.name}`}
          >
            <Trash2 className="size-3.5" />
          </button>
        ),
      },
    ],
    [],
  )

  return (
    <section data-slot="collection-list" className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-foreground">Collections</h1>
          <p className="text-sm text-muted-foreground">
            Manage your document collections
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="size-4" />
          Create Collection
        </Button>
      </div>

      <div className="flex flex-col overflow-hidden rounded-lg border border-border">
        <DataTableFilters
          filters={filters}
          onClearAll={handleClearFilters}
        />
        <DataTable<CollectionResponse>
          data={sortedCollections}
          columns={columns}
          total={total}
          page={page}
          pageSize={pageSize}
          onPageChange={setPage}
          onPageSizeChange={(size) => {
            setPageSize(size)
            setPage(1)
          }}
          loading={loading}
          emptyMessage="No collections found. Create one to get started."
          sortKey={sortKey}
          sortDir={sortDir}
          onSort={handleSort}
          className="border-0 rounded-none"
        />
      </div>
      <CollectionCreateDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={() => {
          setCreateOpen(false)
          fetchCollections()
        }}
      />

      <CollectionDeleteDialog
        collection={deleteCollection}
        open={deleteCollection !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteCollection(null)
        }}
        onDeleted={() => {
          setDeleteCollection(null)
          fetchCollections()
        }}
      />
    </section>
  )
}
