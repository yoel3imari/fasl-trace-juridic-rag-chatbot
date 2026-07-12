"use client"

import { type FormEvent, useState } from "react"
import { X, Loader2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { api } from "@/lib/data"
import { cn } from "@/lib/utils"

interface CollectionCreateDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreated: () => void
}

export function CollectionCreateDialog({
  open,
  onOpenChange,
  onCreated,
}: CollectionCreateDialogProps) {
  const [name, setName] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) return

    setSubmitting(true)
    setError(null)

    try {
      await api.createCollection({ name: trimmed })
      setName("")
      onCreated()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create collection")
    } finally {
      setSubmitting(false)
    }
  }

  const handleClose = () => {
    if (submitting) return
    setName("")
    setError(null)
    onOpenChange(false)
  }

  if (!open) return null

  return (
    <div
      data-slot="collection-create-dialog"
      className="fixed inset-0 z-50 flex items-center justify-center"
    >
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={handleClose}
      />

      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="create-dialog-title"
        className={cn(
          "relative z-10 w-full max-w-md rounded-xl border border-border",
          "bg-background p-6 shadow-2xl",
          "animate-in fade-in zoom-in-95 duration-200",
        )}
      >
        <div className="flex items-center justify-between mb-5">
          <h2
            id="create-dialog-title"
            className="text-base font-semibold text-foreground"
          >
            Create Collection
          </h2>
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

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <label
              htmlFor="collection-name"
              className="text-sm font-medium text-foreground"
            >
              Name
            </label>
            <input
              id="collection-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., Delaware Corp Law 2024"
              maxLength={255}
              required
              autoFocus
              disabled={submitting}
              className={cn(
                "h-9 rounded-md border border-input bg-muted px-3 text-sm text-foreground",
                "outline-none transition-colors",
                "placeholder:text-muted-foreground/60",
                "focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30",
                "disabled:opacity-50",
              )}
            />
            <p className="text-xs text-muted-foreground">
              {name.length}/255 characters
            </p>
          </div>

          {error && (
            <div className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error}
            </div>
          )}

          <div className="flex items-center justify-end gap-2 pt-1">
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
              type="submit"
              size="sm"
              disabled={submitting || !name.trim()}
            >
              {submitting && (
                <Loader2 className="size-3.5 animate-spin" />
              )}
              {submitting ? "Creating..." : "Create"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}
