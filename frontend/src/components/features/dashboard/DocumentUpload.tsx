"use client"

import { type DragEvent, useRef, useState } from "react"
import { Upload, File, X, Loader2 } from "lucide-react"

import { api } from "@/lib/data"
import { Button } from "@/components/ui/button"

const MAX_FILE_SIZE = 50 * 1024 * 1024
const ACCEPTED_TYPE = "application/pdf"

function DocumentUpload({
  open,
  onOpenChange,
  onUploaded,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onUploaded: () => void
}) {
  const [file, setFile] = useState<File | null>(null)
  const [language, setLanguage] = useState("en")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  if (!open) return null

  function validateFile(f: File): string | null {
    if (!f) return "No file selected"
    if (f.size === 0) return "File is empty"
    if (f.size > MAX_FILE_SIZE) return "File size must not exceed 50MB"
    if (f.type !== ACCEPTED_TYPE) return "File must be a PDF"
    return null
  }

  function handleFile(f: File) {
    const validationError = validateFile(f)
    if (validationError) {
      setError(validationError)
      setFile(null)
    } else {
      setError(null)
      setFile(f)
    }
  }

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault()
    setDragOver(false)
    const droppedFile = e.dataTransfer.files[0]
    if (droppedFile) handleFile(droppedFile)
  }

  function handleDragOver(e: DragEvent<HTMLDivElement>) {
    e.preventDefault()
    setDragOver(true)
  }

  function handleDragLeave() {
    setDragOver(false)
  }

  function handleInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    const selectedFile = e.target.files?.[0]
    if (selectedFile) handleFile(selectedFile)
  }

  function clearFile() {
    setFile(null)
    setError(null)
    if (inputRef.current) inputRef.current.value = ""
  }

  async function handleSubmit() {
    if (!file) return
    setLoading(true)
    setError(null)

    try {
      const doc = await api.uploadDocument(file, language)
      await api.processDocument(doc.id)
      onUploaded()
      resetState()
      onOpenChange(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed")
    } finally {
      setLoading(false)
    }
  }

  function resetState() {
    setFile(null)
    setLanguage("en")
    setError(null)
    if (inputRef.current) inputRef.current.value = ""
  }

  function handleClose() {
    resetState()
    onOpenChange(false)
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={handleClose}
    >
      <div
        className="w-full max-w-md rounded-lg border border-border bg-background p-6 shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-base font-semibold text-foreground">Upload Document</h3>
          <button
            onClick={handleClose}
            className="flex size-6 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            aria-label="Close"
          >
            <X className="size-4" />
          </button>
        </div>

        {!file ? (
          <div
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onClick={() => inputRef.current?.click()}
            className={[
              "flex cursor-pointer flex-col items-center gap-3 rounded-lg border-2 border-dashed p-8 transition-colors",
              dragOver
                ? "border-primary bg-primary/5"
                : "border-border hover:border-muted-foreground/40 hover:bg-muted/30",
            ].join(" ")}
          >
            <Upload className="size-8 text-muted-foreground" />
            <div className="text-center">
              <p className="text-sm font-medium text-foreground">
                Drop your PDF here or click to browse
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                PDF only, max 50MB
              </p>
            </div>
            <input
              ref={inputRef}
              type="file"
              accept=".pdf,application/pdf"
              className="hidden"
              onChange={handleInputChange}
            />
          </div>
        ) : (
          <div className="flex items-center gap-3 rounded-lg border border-border bg-muted/30 p-3">
            <div className="flex size-10 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
              <File className="size-5" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-foreground">
                {file.name}
              </p>
              <p className="text-xs text-muted-foreground">
                {(file.size / 1024 / 1024).toFixed(1)} MB
              </p>
            </div>
            <button
              onClick={clearFile}
              className="flex size-6 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              aria-label="Remove file"
            >
              <X className="size-4" />
            </button>
          </div>
        )}

        <div className="mt-4">
          <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
            Language
          </label>
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            className="h-8 w-full rounded-md border border-input bg-muted px-2.5 text-xs text-foreground outline-none transition-colors focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30"
          >
            <option value="en">English</option>
            <option value="fr">French</option>
            <option value="ar">Arabic</option>
          </select>
        </div>

        {error && (
          <p className="mt-3 text-xs text-rose-500">{error}</p>
        )}

        <div className="mt-5 flex items-center justify-end gap-2">
          <Button variant="outline" size="sm" onClick={handleClose} disabled={loading}>
            Cancel
          </Button>
          <Button
            variant="default"
            size="sm"
            onClick={handleSubmit}
            disabled={!file || loading}
          >
            {loading ? (
              <>
                <Loader2 className="size-3.5 animate-spin" />
                Uploading...
              </>
            ) : (
              "Upload & Process"
            )}
          </Button>
        </div>
      </div>
    </div>
  )
}

export { DocumentUpload }
