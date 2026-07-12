"use client"

import { useCallback, useEffect, useState } from "react"
import { Loader2, X, Check } from "lucide-react"

import { api, type CollectionResponse, type CollectionListResponse } from "@/lib/data"
import { Button } from "@/components/ui/button"

function DocumentAssignToCollection({
  document,
  open,
  onOpenChange,
  onAssigned,
}: {
  document: { id: string; filename: string } | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onAssigned: () => void
}) {
  const [collections, setCollections] = useState<CollectionResponse[]>([])
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(false)
  const [assigning, setAssigning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  const fetchCollections = useCallback(async () => {
    setLoading(true)
    try {
      const result: CollectionListResponse = await api.listCollections({ skip: 0, limit: 100 })
      setCollections(result.collections)
    } catch {
      setCollections([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (open) {
      fetchCollections()
      setSelectedIds(new Set())
      setError(null)
      setSuccess(false)
    }
  }, [open, fetchCollections])

  function toggleCollection(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  async function handleAssign() {
    if (!document || selectedIds.size === 0) return
    setAssigning(true)
    setError(null)

    try {
      const promises = Array.from(selectedIds).map((collectionId) =>
        api.addDocumentsToCollection(collectionId, [document.id]),
      )
      await Promise.all(promises)
      setSuccess(true)
      setTimeout(() => {
        onAssigned()
        onOpenChange(false)
      }, 800)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to assign document")
    } finally {
      setAssigning(false)
    }
  }

  if (!open || !document) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={() => onOpenChange(false)}
    >
      <div
        className="w-full max-w-md rounded-lg border border-border bg-background p-6 shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-base font-semibold text-foreground">Assign to Collection</h3>
          <button
            onClick={() => onOpenChange(false)}
            className="flex size-6 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            aria-label="Close"
          >
            <X className="size-4" />
          </button>
        </div>

        <div className="mb-4 rounded-md border border-border bg-muted/30 px-3 py-2">
          <p className="text-xs text-muted-foreground">Document</p>
          <p className="text-sm font-medium text-foreground">{document.filename}</p>
        </div>

        {success ? (
          <div className="flex flex-col items-center gap-3 py-8">
            <div className="flex size-12 items-center justify-center rounded-full bg-emerald-500/10">
              <Check className="size-6 text-emerald-500" />
            </div>
            <p className="text-sm font-medium text-foreground">
              Document assigned successfully
            </p>
          </div>
        ) : loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="size-5 animate-spin text-muted-foreground" />
          </div>
        ) : collections.length === 0 ? (
          <div className="rounded-md border border-border bg-muted/20 px-4 py-6 text-center">
            <p className="text-sm text-muted-foreground">No collections available.</p>
            <p className="mt-1 text-xs text-muted-foreground/60">
              Create a collection first to assign documents.
            </p>
          </div>
        ) : (
          <div className="max-h-[240px] space-y-1 overflow-y-auto">
            {collections.map((collection) => {
              const isSelected = selectedIds.has(collection.id)
              return (
                <label
                  key={collection.id}
                  className={[
                    "flex cursor-pointer items-center gap-3 rounded-md border px-3 py-2.5 transition-colors",
                    isSelected
                      ? "border-primary/40 bg-primary/5"
                      : "border-transparent hover:bg-muted/50",
                  ].join(" ")}
                >
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={() => toggleCollection(collection.id)}
                    className="size-4 accent-primary"
                  />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-foreground">{collection.name}</p>
                    <p className="text-xs text-muted-foreground">
                      Created {new Date(collection.created_at).toLocaleDateString()}
                    </p>
                  </div>
                </label>
              )
            })}
          </div>
        )}

        {error && (
          <p className="mt-3 text-xs text-rose-500">{error}</p>
        )}

        <div className="mt-5 flex items-center justify-end gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => onOpenChange(false)}
            disabled={assigning}
          >
            {success ? "Close" : "Cancel"}
          </Button>
          {!success && (
            <Button
              variant="default"
              size="sm"
              onClick={handleAssign}
              disabled={selectedIds.size === 0 || assigning}
            >
              {assigning ? (
                <>
                  <Loader2 className="size-3.5 animate-spin" />
                  Assigning...
                </>
              ) : (
                `Assign to ${selectedIds.size} collection${selectedIds.size !== 1 ? "s" : ""}`
              )}
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}

export { DocumentAssignToCollection }
