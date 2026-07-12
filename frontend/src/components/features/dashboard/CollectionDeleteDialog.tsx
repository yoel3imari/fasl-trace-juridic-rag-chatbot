"use client"

import { useState } from "react"
import { Loader2, Trash2, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import { api } from "@/lib/data"
import { cn } from "@/lib/utils"

interface CollectionDeleteDialogProps {
  collection: { id: string; name: string } | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onDeleted: () => void
}

export function CollectionDeleteDialog({
  collection,
  open,
  onOpenChange,
  onDeleted,
}: CollectionDeleteDialogProps) {
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleConfirm = async () => {
    if (!collection) return

    setSubmitting(true)
    setError(null)

    try {
      await api.deleteCollection(collection.id)
      onDeleted()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete collection")
    } finally {
      setSubmitting(false)
    }
  }

  const handleClose = () => {
    if (submitting) return
    setError(null)
    onOpenChange(false)
  }

  if (!open || !collection) return null

  return (
    <div
      data-slot="collection-delete-dialog"
      className="fixed inset-0 z-50 flex items-center justify-center"
    >
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={handleClose}
      />

      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="delete-dialog-title"
        aria-describedby="delete-dialog-desc"
        className={cn(
          "relative z-10 w-full max-w-sm rounded-xl border border-border",
          "bg-background p-6 shadow-2xl",
          "animate-in fade-in zoom-in-95 duration-200",
        )}
      >
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-destructive/10">
              <Trash2 className="size-4 text-destructive" />
            </div>
            <div>
              <h2
                id="delete-dialog-title"
                className="text-base font-semibold text-foreground"
              >
                Delete Collection
              </h2>
              <p id="delete-dialog-desc" className="text-sm text-muted-foreground mt-0.5">
                Are you sure you want to delete{" "}
                <span className="font-medium text-foreground">
                  {collection.name}
                </span>
                ?
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={handleClose}
            disabled={submitting}
            className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-50"
            aria-label="Close"
          >
            <X className="size-4" />
          </button>
        </div>

        <p className="mb-4 rounded-md bg-muted px-3 py-2 text-xs text-muted-foreground">
          This action cannot be undone. All documents in this collection will
          be disassociated.
        </p>

        {error && (
          <div className="mb-4 rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </div>
        )}

        <div className="flex items-center justify-end gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={submitting}
            onClick={handleClose}
          >
            Cancel
          </Button>
          <Button
            type="button"
            variant="destructive"
            size="sm"
            disabled={submitting}
            onClick={handleConfirm}
          >
            {submitting && (
              <Loader2 className="size-3.5 animate-spin" />
            )}
            {submitting ? "Deleting..." : "Delete"}
          </Button>
        </div>
      </div>
    </div>
  )
}
