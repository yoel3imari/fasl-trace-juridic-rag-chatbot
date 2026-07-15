"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { MoreHorizontal, Plus, FileText, FolderOpen, XCircle, Trash2 } from "lucide-react"

import { api, type DocumentResponse, type DocumentListResponse } from "@/lib/data"
import { Button } from "@/components/ui/button"
import { DataTable, type Column } from "@/components/ui/data-table/DataTable"
import { DataTableFilters, type FilterConfig } from "@/components/ui/data-table/DataTableFilters"
import { IngestionStatusBadge } from "@/components/features/dashboard/IngestionStatusBadge"
import { DocumentUpload } from "@/components/features/dashboard/DocumentUpload"
import { DocumentErrorDialog } from "@/components/features/dashboard/DocumentErrorDialog"
import { DocumentAssignToCollection } from "@/components/features/dashboard/DocumentAssignToCollection"

const PAGE_SIZES = [10, 25, 50]

const languageLabels: Record<string, string> = {
  en: "EN",
  fr: "FR",
  ar: "AR",
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr)
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  })
}

interface DetailViewProps {
  document: DocumentResponse
  onClose: () => void
}

function DetailView({ document, onClose }: DetailViewProps) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg rounded-lg border border-border bg-background p-6 shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="mb-4 text-base font-semibold text-foreground">Document Details</h3>
        <dl className="space-y-3 text-sm">
          <div className="flex justify-between">
            <dt className="text-muted-foreground">Filename</dt>
            <dd className="text-foreground">{document.filename}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-muted-foreground">Language</dt>
            <dd className="text-foreground">{languageLabels[document.language] ?? document.language}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-muted-foreground">Status</dt>
            <dd>
              <IngestionStatusBadge status={document.status} />
            </dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-muted-foreground">Pages</dt>
            <dd className="text-foreground">{document.page_count ?? "—"}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-muted-foreground">Created</dt>
            <dd className="text-foreground">{formatDate(document.created_at)}</dd>
          </div>
          {document.updated_at && (
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Updated</dt>
              <dd className="text-foreground">{formatDate(document.updated_at)}</dd>
            </div>
          )}
          {document.detected_languages && document.detected_languages.length > 0 && (
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Detected Languages</dt>
              <dd className="text-foreground">
                {document.detected_languages
                  .map((l) => languageLabels[l] ?? l)
                  .join(", ")}
              </dd>
            </div>
          )}
        </dl>
        <div className="mt-6 flex justify-end">
          <Button variant="outline" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </div>
  )
}

function DocumentTable() {
  const [documents, setDocuments] = useState<DocumentResponse[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [search, setSearch] = useState("")
  const [statusFilter, setStatusFilter] = useState("")
  const [languageFilter, setLanguageFilter] = useState("")
  const [sortKey, setSortKey] = useState<string | undefined>("updated_at")
  const [sortDir, setSortDir] = useState<"asc" | "desc" | undefined>("desc")

  const [dropdownAnchor, setDropdownAnchor] = useState<{
    doc: DocumentResponse
    top: number
    right: number
  } | null>(null)

  const [uploadOpen, setUploadOpen] = useState(false)
  const [errorDoc, setErrorDoc] = useState<DocumentResponse | null>(null)
  const [errorDialogOpen, setErrorDialogOpen] = useState(false)
  const [assignDoc, setAssignDoc] = useState<DocumentResponse | null>(null)
  const [assignDialogOpen, setAssignDialogOpen] = useState(false)
  const [detailDoc, setDetailDoc] = useState<DocumentResponse | null>(null)
  const [deleteDocId, setDeleteDocId] = useState<string | null>(null)
  const [deleting, setDeleting] = useState(false)

  const fetchDocuments = useCallback(async () => {
    setLoading(true)
    try {
      const skip = (page - 1) * pageSize
      const result: DocumentListResponse = await api.listDocuments({
        skip,
        limit: pageSize,
        status: (statusFilter || undefined) as "pending" | "processing" | "processed" | "failed" | undefined,
        language: (languageFilter || undefined) as "en" | "fr" | "ar" | undefined,
        search: search || undefined,
      })
      setDocuments(result.documents)
      setTotal(result.total)
    } catch {
      setDocuments([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }, [page, pageSize, search, statusFilter, languageFilter])

  useEffect(() => {
    fetchDocuments()
  }, [fetchDocuments])

  const sortedDocuments = useMemo(() => {
    if (!sortKey || !sortDir) return documents
    return [...documents].sort((a, b) => {
      let aVal: string | number = ""
      let bVal: string | number = ""

      if (sortKey === "updated_at" || sortKey === "created_at") {
        aVal = new Date(a[sortKey] ?? a.created_at).getTime()
        bVal = new Date(b[sortKey] ?? b.created_at).getTime()
      } else if (sortKey === "filename") {
        aVal = a.filename.toLowerCase()
        bVal = b.filename.toLowerCase()
      }

      if (aVal < bVal) return sortDir === "asc" ? -1 : 1
      if (aVal > bVal) return sortDir === "asc" ? 1 : -1
      return 0
    })
  }, [documents, sortKey, sortDir])

  useEffect(() => {
    if (!dropdownAnchor) return
    function handleClickOutside(e: MouseEvent) {
      const target = e.target as Node
      const dropdown = document.getElementById("doc-table-dropdown")
      if (dropdown && !dropdown.contains(target)) {
        setDropdownAnchor(null)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [dropdownAnchor])

  // Recalculate position on scroll/resize to keep dropdown anchored
  useEffect(() => {
    if (!dropdownAnchor) return
    const handleMove = () => setDropdownAnchor(null)
    window.addEventListener("scroll", handleMove, true)
    window.addEventListener("resize", handleMove)
    return () => {
      window.removeEventListener("scroll", handleMove, true)
      window.removeEventListener("resize", handleMove)
    }
  }, [dropdownAnchor])

  const handleFilterChange = useCallback((key: string, value: string) => {
    setPage(1)
    switch (key) {
      case "search":
        setSearch(value)
        break
      case "status":
        setStatusFilter(value)
        break
      case "language":
        setLanguageFilter(value)
        break
    }
  }, [])

  const handleClearAll = useCallback(() => {
    setPage(1)
    setSearch("")
    setStatusFilter("")
    setLanguageFilter("")
  }, [])

  const handleProcess = useCallback(async (id: string) => {
    setDropdownAnchor(null)
    try {
      await api.processDocument(id)
      const skip = (page - 1) * pageSize
      const result = await api.listDocuments({
        skip,
        limit: pageSize,
        status: (statusFilter || undefined) as "pending" | "processing" | "processed" | "failed" | undefined,
        language: (languageFilter || undefined) as "en" | "fr" | "ar" | undefined,
        search: search || undefined,
      })
      setDocuments(result.documents)
      setTotal(result.total)
    } catch {
      // processDocument may update status asynchronously
    }
  }, [page, pageSize, statusFilter, languageFilter, search])

  const handleUploaded = useCallback(() => {
    fetchDocuments()
  }, [fetchDocuments])

  const handleAssigned = useCallback(() => {
    fetchDocuments()
  }, [fetchDocuments])

  const handleViewError = useCallback((doc: DocumentResponse) => {
    setDropdownAnchor(null)
    setErrorDoc(doc)
    setErrorDialogOpen(true)
  }, [])

  const handleAssignToCollection = useCallback((doc: DocumentResponse) => {
    setDropdownAnchor(null)
    setAssignDoc(doc)
    setAssignDialogOpen(true)
  }, [])

  const handleViewDetails = useCallback((doc: DocumentResponse) => {
    setDropdownAnchor(null)
    setDetailDoc(doc)
  }, [])

  const handleDelete = useCallback(async () => {
    if (!deleteDocId) return
    setDeleting(true)
    try {
      await api.deleteDocument(deleteDocId)
      setDeleteDocId(null)
      fetchDocuments()
    } catch {
    } finally {
      setDeleting(false)
    }
  }, [deleteDocId, fetchDocuments])

  const filters: FilterConfig[] = [
    {
      key: "search",
      label: "filename",
      type: "search",
      value: search,
      onChange: handleFilterChange,
    },
    {
      key: "status",
      label: "Status",
      type: "select",
      value: statusFilter,
      onChange: handleFilterChange,
      options: [
        { label: "Pending", value: "pending" },
        { label: "Processing", value: "processing" },
        { label: "Processed", value: "processed" },
        { label: "Failed", value: "failed" },
      ],
    },
    {
      key: "language",
      label: "Language",
      type: "select",
      value: languageFilter,
      onChange: handleFilterChange,
      options: [
        { label: "English", value: "en" },
        { label: "French", value: "fr" },
        { label: "Arabic", value: "ar" },
      ],
    },
  ]

  const columns: Column<DocumentResponse>[] = [
    {
      key: "filename",
      header: "Filename",
      sortable: true,
      width: "30%",
      render: (doc) => (
        <span className="flex items-center gap-2 text-sm font-medium text-foreground">
          <FileText className="size-3.5 shrink-0 text-muted-foreground" />
          <span className="truncate max-w-[300px]" title={doc.filename}>
            {doc.filename}
          </span>
        </span>
      ),
    },
    {
      key: "language",
      header: "Language",
      width: "10%",
      render: (doc) => {
        const label = languageLabels[doc.language] ?? doc.language.toUpperCase()
        return (
          <span className="inline-flex items-center rounded border border-border/60 bg-muted/50 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
            {label}
          </span>
        )
      },
    },
    {
      key: "status",
      header: "Status",
      width: "15%",
      render: (doc) => <IngestionStatusBadge status={doc.status} />,
    },
    {
      key: "page_count",
      header: "Pages",
      width: "8%",
      render: (doc) => (
        <span className="text-sm text-muted-foreground">{doc.page_count ?? "—"}</span>
      ),
    },
    {
      key: "created_at",
      header: "Created",
      sortable: true,
      width: "15%",
      render: (doc) => (
        <span className="text-sm text-muted-foreground">{formatDate(doc.created_at)}</span>
      ),
    },
    {
      key: "actions",
      header: "",
      width: "5%",
      render: (doc) => (
        <div className="relative flex justify-end">
          <button
            onClick={(e) => {
              e.stopPropagation()
              const rect = e.currentTarget.getBoundingClientRect()
              if (dropdownAnchor?.doc.id === doc.id) {
                setDropdownAnchor(null)
              } else {
                setDropdownAnchor({
                  doc,
                  top: rect.bottom + 4,
                  right: document.documentElement.clientWidth - rect.right,
                })
              }
            }}
            className="flex size-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            aria-label="Actions"
          >
            <MoreHorizontal className="size-4" />
          </button>
        </div>
      ),
    },
  ]

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-foreground">Documents</h2>
        <Button variant="default" size="sm" onClick={() => setUploadOpen(true)}>
          <Plus className="size-4" />
          Upload Document
        </Button>
      </div>

      <DataTableFilters
        filters={filters}
        onClearAll={handleClearAll}
      />
      <DataTable<DocumentResponse>
        data={sortedDocuments}
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
        emptyMessage="No documents found. Upload a document to get started."
        sortKey={sortKey}
        sortDir={sortDir}
        onSort={(key, dir) => {
          setSortKey(key)
          setSortDir(dir)
        }}
      />

      <DocumentUpload
        open={uploadOpen}
        onOpenChange={setUploadOpen}
        onUploaded={handleUploaded}
      />
      {errorDoc && (
        <DocumentErrorDialog
          document={errorDoc}
          open={errorDialogOpen}
          onOpenChange={(open) => {
            setErrorDialogOpen(open)
            if (!open) setErrorDoc(null)
          }}
        />
      )}
      {assignDoc && (
        <DocumentAssignToCollection
          document={assignDoc}
          open={assignDialogOpen}
          onOpenChange={(open) => {
            setAssignDialogOpen(open)
            if (!open) setAssignDoc(null)
          }}
          onAssigned={handleAssigned}
        />
      )}
      {detailDoc && (
        <DetailView
          document={detailDoc}
          onClose={() => setDetailDoc(null)}
        />
      )}

      {deleteDocId && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
          onClick={() => !deleting && setDeleteDocId(null)}
        >
          <div
            className="w-full max-w-sm rounded-lg border border-border bg-background p-6 shadow-lg"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="mb-2 text-base font-semibold text-foreground">Delete Document</h3>
            <p className="text-sm text-muted-foreground">
              This will permanently delete the document, its chunks, and vector embeddings. This action cannot be undone.
            </p>
            <div className="mt-6 flex justify-end gap-3">
              <Button variant="outline" size="sm" disabled={deleting} onClick={() => setDeleteDocId(null)}>
                Cancel
              </Button>
              <Button variant="destructive" size="sm" disabled={deleting} onClick={handleDelete}>
                {deleting ? "Deleting..." : "Delete"}
              </Button>
            </div>
          </div>
        </div>
      )}

      {dropdownAnchor && (
        <div
          id="doc-table-dropdown"
          style={{ position: "fixed", top: dropdownAnchor.top, right: dropdownAnchor.right, zIndex: 50 }}
          className="min-w-[180px] overflow-hidden rounded-lg border border-border bg-popover py-1 shadow-lg"
        >
          {(dropdownAnchor.doc.status === "pending" || dropdownAnchor.doc.status === "failed") && (
            <button
              onClick={() => handleProcess(dropdownAnchor.doc.id)}
              className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs text-foreground transition-colors hover:bg-muted"
            >
              <FolderOpen className="size-3.5 text-muted-foreground" />
              Process
            </button>
          )}
          <button
            onClick={() => handleAssignToCollection(dropdownAnchor.doc)}
            className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs text-foreground transition-colors hover:bg-muted"
          >
            <FolderOpen className="size-3.5 text-muted-foreground" />
            Assign to Collection
          </button>
          <button
            onClick={() => handleViewDetails(dropdownAnchor.doc)}
            className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs text-foreground transition-colors hover:bg-muted"
          >
            <FileText className="size-3.5 text-muted-foreground" />
            View Details
          </button>
          {dropdownAnchor.doc.status === "failed" && (
            <button
              onClick={() => handleViewError(dropdownAnchor.doc)}
              className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs text-foreground transition-colors hover:bg-muted"
            >
              <XCircle className="size-3.5 text-rose-400" />
              View Error
            </button>
          )}
          <div className="my-1 border-t border-border" />
          <button
            onClick={() => {
              setDeleteDocId(dropdownAnchor.doc.id)
              setDropdownAnchor(null)
            }}
            className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs text-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
          >
            <Trash2 className="size-3.5 text-destructive/70" />
            Delete
          </button>
        </div>
      )}
    </div>
  )
}

export { DocumentTable }
