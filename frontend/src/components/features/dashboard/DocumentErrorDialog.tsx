"use client"

import { XCircle, X } from "lucide-react"

import { Button } from "@/components/ui/button"

function DocumentErrorDialog({
  document,
  open,
  onOpenChange,
}: {
  document: { id: string; filename: string; error_log?: Record<string, unknown> | null } | null
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  if (!open || !document) return null

  const errorLog = document.error_log

  function renderErrorValue(value: unknown): string {
    if (typeof value === "string") return value
    if (typeof value === "number" || typeof value === "boolean") return String(value)
    if (value === null) return "—"
    if (Array.isArray(value)) return value.join(", ")
    return JSON.stringify(value)
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={() => onOpenChange(false)}
    >
      <div
        className="w-full max-w-lg rounded-lg border border-border bg-background p-6 shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <XCircle className="size-5 text-rose-500" />
            <h3 className="text-base font-semibold text-foreground">Error Details</h3>
          </div>
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

        {errorLog && typeof errorLog === "object" && Object.keys(errorLog).length > 0 ? (
          <div className="space-y-3">
            {Object.entries(errorLog).map(([key, value]) => (
              <div key={key}>
                <p className="mb-0.5 text-xs font-medium capitalize text-muted-foreground">
                  {key.replace(/_/g, " ")}
                </p>
                <div className="rounded-md border border-border bg-muted/20 px-3 py-2">
                  <p className="break-words font-mono text-xs text-foreground">
                    {renderErrorValue(value)}
                  </p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded-md border border-border bg-muted/20 px-3 py-4 text-center">
            <p className="text-sm text-muted-foreground">No error details available</p>
          </div>
        )}

        <div className="mt-6 flex justify-end">
          <Button variant="outline" size="sm" onClick={() => onOpenChange(false)}>
            Close
          </Button>
        </div>
      </div>
    </div>
  )
}

export { DocumentErrorDialog }
