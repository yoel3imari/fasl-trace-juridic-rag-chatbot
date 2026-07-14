"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { Pencil, Plus, Power, PowerOff, Trash2, Wifi, WifiOff, X, Loader2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { DataTable, type Column } from "@/components/ui/data-table/DataTable"
import { api } from "@/lib/data"
import type {
  ModelAssignmentResponse,
  LlmProviderResponse,
} from "@/lib/data"
import { cn } from "@/lib/utils"

const PROVIDER_LABELS: Record<string, string> = {
  openai: "OpenAI",
  anthropic: "Anthropic",
  ollama: "Ollama",
}

const FUNCTION_LABELS: Record<string, string> = {
  retrieval: "Retrieval",
  generation: "Generation",
  evaluation: "Evaluation",
}

const FUNCTION_CLASSES: Record<string, string> = {
  retrieval: "bg-sky-500/10 text-sky-500",
  generation: "bg-violet-500/10 text-violet-500",
  evaluation: "bg-amber-500/10 text-amber-500",
}

function StatusBadge({ active }: { active: boolean }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium leading-none",
        active
          ? "bg-emerald-500/10 text-emerald-500"
          : "bg-rose-500/10 text-rose-500",
      )}
    >
      <span
        className={cn(
          "size-1.5 rounded-full",
          active ? "bg-emerald-500" : "bg-rose-500",
        )}
      />
      {active ? "Active" : "Inactive"}
    </span>
  )
}

function HealthBadge({
  status,
  message,
}: {
  status?: string | null
  message?: string | null
}) {
  if (!status) {
    return <span className="text-muted-foreground">&mdash;</span>
  }

  const isVerified = status === "verified"
  return (
    <span
      title={message ?? undefined}
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium leading-none",
        isVerified
          ? "bg-emerald-500/10 text-emerald-500"
          : "bg-rose-500/10 text-rose-500",
      )}
    >
      {isVerified ? (
        <Wifi className="size-3" />
      ) : (
        <WifiOff className="size-3" />
      )}
      {isVerified ? "Verified" : "Unreachable"}
    </span>
  )
}

function FunctionBadge({ fn }: { fn: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium leading-none",
        FUNCTION_CLASSES[fn] ?? "bg-muted text-muted-foreground",
      )}
    >
      {FUNCTION_LABELS[fn] ?? fn}
    </span>
  )
}

/* ------------------------------------------------------------------ */
/*  Add Assignment Dialog                                              */
/* ------------------------------------------------------------------ */

interface AddAssignmentDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreated: () => void
}

function AddAssignmentDialog({
  open,
  onOpenChange,
  onCreated,
}: AddAssignmentDialogProps) {
  const [providers, setProviders] = useState<LlmProviderResponse[]>([])
  const [loadingProviders, setLoadingProviders] = useState(false)

  const [providerId, setProviderId] = useState("")
  const [modelName, setModelName] = useState("")
  const [systemFunction, setSystemFunction] = useState<
    "retrieval" | "generation" | "evaluation" | ""
  >("")
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    setProviderId("")
    setModelName("")
    setSystemFunction("")
    setError(null)

    setLoadingProviders(true)
    api
      .listLlmProviders({ skip: 0, limit: 100 })
      .then((result) => {
        setProviders(result.items.filter((p) => p.is_active))
      })
      .catch(() => {
        setProviders([])
      })
      .finally(() => setLoadingProviders(false))
  }, [open])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!providerId || !modelName.trim() || !systemFunction) return

    setSubmitting(true)
    setError(null)

    try {
      await api.createModelAssignment({
        provider_id: providerId,
        model_name: modelName.trim(),
        system_function: systemFunction,
      })
      onCreated()
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to create assignment",
      )
    } finally {
      setSubmitting(false)
    }
  }

  const handleClose = () => {
    if (submitting) return
    setError(null)
    onOpenChange(false)
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={handleClose}
      />

      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="add-assignment-dialog-title"
        className={cn(
          "relative z-10 w-full max-w-md rounded-xl border border-border",
          "bg-background p-6 shadow-2xl",
          "animate-in fade-in zoom-in-95 duration-200",
        )}
      >
        <div className="mb-5 flex items-center justify-between">
          <h2
            id="add-assignment-dialog-title"
            className="text-base font-semibold text-foreground"
          >
            Add Assignment
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
              htmlFor="assignment-provider"
              className="text-sm font-medium text-foreground"
            >
              Provider
            </label>
            {loadingProviders ? (
              <div className="flex h-9 items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="size-3.5 animate-spin" />
                Loading providers...
              </div>
            ) : (
              <select
                id="assignment-provider"
                value={providerId}
                onChange={(e) => setProviderId(e.target.value)}
                required
                disabled={submitting || providers.length === 0}
                autoFocus
                className="h-9 rounded-md border border-input bg-muted px-3 text-sm text-foreground outline-none transition-colors focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30 disabled:opacity-50"
              >
                <option value="">
                  {providers.length === 0
                    ? "No active providers"
                    : "Select provider..."}
                </option>
                {providers.map((p) => (
                  <option key={p.id} value={p.id}>
                    {PROVIDER_LABELS[p.provider_type] ?? p.provider_type}
                    {p.base_url ? ` (${p.base_url})` : ""}
                  </option>
                ))}
              </select>
            )}
          </div>

          <div className="flex flex-col gap-1.5">
            <label
              htmlFor="assignment-model"
              className="text-sm font-medium text-foreground"
            >
              Model Name
            </label>
            <input
              id="assignment-model"
              type="text"
              value={modelName}
              onChange={(e) => setModelName(e.target.value)}
              placeholder="e.g., gpt-4o, claude-3-5-sonnet, llama3"
              required
              disabled={submitting}
              className="h-9 rounded-md border border-input bg-muted px-3 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground/60 focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30 disabled:opacity-50"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label
              htmlFor="assignment-function"
              className="text-sm font-medium text-foreground"
            >
              System Function
            </label>
            <select
              id="assignment-function"
              value={systemFunction}
              onChange={(e) =>
                setSystemFunction(
                  e.target.value as
                    | "retrieval"
                    | "generation"
                    | "evaluation"
                    | "",
                )
              }
              required
              disabled={submitting}
              className="h-9 rounded-md border border-input bg-muted px-3 text-sm text-foreground outline-none transition-colors focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30 disabled:opacity-50"
            >
              <option value="">Select function...</option>
              <option value="retrieval">Retrieval</option>
              <option value="generation">Generation</option>
              <option value="evaluation">Evaluation</option>
            </select>
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
              disabled={
                submitting ||
                !providerId ||
                !modelName.trim() ||
                !systemFunction
              }
            >
              {submitting && (
                <Loader2 className="size-3.5 animate-spin" />
              )}
              {submitting ? "Adding..." : "Add Assignment"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Delete Assignment Dialog                                           */
/* ------------------------------------------------------------------ */

interface DeleteAssignmentDialogProps {
  assignment: ModelAssignmentResponse | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onDeleted: () => void
}

function DeleteAssignmentDialog({
  assignment,
  open,
  onOpenChange,
  onDeleted,
}: DeleteAssignmentDialogProps) {
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleConfirm = async () => {
    if (!assignment) return

    setSubmitting(true)
    setError(null)

    try {
      await api.deleteModelAssignment(assignment.id)
      onDeleted()
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to delete assignment",
      )
    } finally {
      setSubmitting(false)
    }
  }

  const handleClose = () => {
    if (submitting) return
    setError(null)
    onOpenChange(false)
  }

  if (!open || !assignment) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={handleClose}
      />

      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="delete-assignment-dialog-title"
        aria-describedby="delete-assignment-dialog-desc"
        className={cn(
          "relative z-10 w-full max-w-sm rounded-xl border border-border",
          "bg-background p-6 shadow-2xl",
          "animate-in fade-in zoom-in-95 duration-200",
        )}
      >
        <div className="mb-4 flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-destructive/10">
              <Trash2 className="size-4 text-destructive" />
            </div>
            <div>
              <h2
                id="delete-assignment-dialog-title"
                className="text-base font-semibold text-foreground"
              >
                Delete Assignment
              </h2>
              <p
                id="delete-assignment-dialog-desc"
                className="mt-0.5 text-sm text-muted-foreground"
              >
                Are you sure you want to delete{" "}
                <span className="font-medium text-foreground">
                  {assignment.model_name}
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
          This action cannot be undone. The model will no longer be
          available for this system function.
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

/* ------------------------------------------------------------------ */
/*  Edit Assignment Dialog                                             */
/* ------------------------------------------------------------------ */

interface EditAssignmentDialogProps {
  assignment: ModelAssignmentResponse | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onUpdated: () => void
  allProviders: LlmProviderResponse[]
}

function EditAssignmentDialog({
  assignment,
  open,
  onOpenChange,
  onUpdated,
  allProviders,
}: EditAssignmentDialogProps) {
  const [providerId, setProviderId] = useState("")
  const [modelName, setModelName] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open || !assignment) return
    setProviderId(assignment.provider_id)
    setModelName(assignment.model_name)
    setError(null)
  }, [open, assignment])

  const activeProviders = useMemo(
    () => allProviders.filter((p) => p.is_active),
    [allProviders],
  )

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!assignment || !providerId || !modelName.trim()) return

    setSubmitting(true)
    setError(null)

    try {
      await api.updateModelAssignment(assignment.id, {
        provider_id: providerId,
        model_name: modelName.trim(),
      })
      onUpdated()
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to update assignment",
      )
    } finally {
      setSubmitting(false)
    }
  }

  const handleClose = () => {
    if (submitting) return
    setError(null)
    onOpenChange(false)
  }

  if (!open || !assignment) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={handleClose}
      />

      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="edit-assignment-dialog-title"
        className={cn(
          "relative z-10 w-full max-w-md rounded-xl border border-border",
          "bg-background p-6 shadow-2xl",
          "animate-in fade-in zoom-in-95 duration-200",
        )}
      >
        <div className="mb-5 flex items-center justify-between">
          <h2
            id="edit-assignment-dialog-title"
            className="text-base font-semibold text-foreground"
          >
            Edit Assignment
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
              htmlFor="edit-assignment-provider"
              className="text-sm font-medium text-foreground"
            >
              Provider
            </label>
            <select
              id="edit-assignment-provider"
              value={providerId}
              onChange={(e) => setProviderId(e.target.value)}
              required
              disabled={submitting || activeProviders.length === 0}
              autoFocus
              className="h-9 rounded-md border border-input bg-muted px-3 text-sm text-foreground outline-none transition-colors focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30 disabled:opacity-50"
            >
              <option value="">
                {activeProviders.length === 0
                  ? "No active providers"
                  : "Select provider..."}
              </option>
              {activeProviders.map((p) => (
                <option key={p.id} value={p.id}>
                  {PROVIDER_LABELS[p.provider_type] ?? p.provider_type}
                  {p.base_url ? ` (${p.base_url})` : ""}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1.5">
            <label
              htmlFor="edit-assignment-model"
              className="text-sm font-medium text-foreground"
            >
              Model Name
            </label>
            <input
              id="edit-assignment-model"
              type="text"
              value={modelName}
              onChange={(e) => setModelName(e.target.value)}
              placeholder="e.g., gpt-4o, claude-3-5-sonnet, llama3"
              required
              disabled={submitting}
              className="h-9 rounded-md border border-input bg-muted px-3 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground/60 focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30 disabled:opacity-50"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium text-foreground">
              System Function
            </label>
            <div className="flex h-9 items-center rounded-md border border-input bg-muted px-3 text-sm text-muted-foreground">
              {FUNCTION_LABELS[assignment.system_function] ??
                assignment.system_function}
            </div>
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
              disabled={
                submitting || !providerId || !modelName.trim()
              }
            >
              {submitting && (
                <Loader2 className="size-3.5 animate-spin" />
              )}
              {submitting ? "Saving..." : "Save Changes"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  AssignmentManager                                                  */
/* ------------------------------------------------------------------ */

export function AssignmentManager() {
  const [assignments, setAssignments] = useState<ModelAssignmentResponse[]>(
    [],
  )
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(100)

  const [providerMap, setProviderMap] = useState<
    Record<string, string>
  >({})

  const [allProviders, setAllProviders] = useState<LlmProviderResponse[]>([])

  const [addOpen, setAddOpen] = useState(false)
  const [editAssignment, setEditAssignment] =
    useState<ModelAssignmentResponse | null>(null)
  const [deleteAssignment, setDeleteAssignment] =
    useState<ModelAssignmentResponse | null>(null)
  const [pingLoading, setPingLoading] = useState<Record<string, boolean>>(
    {},
  )
  const [sortKey, setSortKey] = useState<string | undefined>("updated_at")
  const [sortDir, setSortDir] = useState<"asc" | "desc" | undefined>("desc")

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const skip = (page - 1) * pageSize
      const [assignResult, providerResult] = await Promise.all([
        api.listModelAssignments({ skip, limit: pageSize }),
        api.listLlmProviders({ skip: 0, limit: 100 }),
      ])
      setAssignments(assignResult.items)
      setTotal(assignResult.total)

      setAllProviders(providerResult.items)

      const map: Record<string, string> = {}
      for (const p of providerResult.items) {
        map[p.id] =
          PROVIDER_LABELS[p.provider_type] ?? p.provider_type
      }
      setProviderMap(map)
    } catch {
      setAssignments([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }, [page, pageSize])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const sortedAssignments = useMemo(() => {
    if (!sortKey || !sortDir) return assignments
    return [...assignments].sort((a, b) => {
      let aVal: string | number = ""
      let bVal: string | number = ""

      if (sortKey === "updated_at" || sortKey === "created_at") {
        aVal = new Date(a[sortKey] ?? a.created_at).getTime()
        bVal = new Date(b[sortKey] ?? b.created_at).getTime()
      } else if (sortKey === "model_name") {
        aVal = a.model_name.toLowerCase()
        bVal = b.model_name.toLowerCase()
      }

      if (aVal < bVal) return sortDir === "asc" ? -1 : 1
      if (aVal > bVal) return sortDir === "asc" ? 1 : -1
      return 0
    })
  }, [assignments, sortKey, sortDir])

  const columns: Column<ModelAssignmentResponse>[] = useMemo(
    () => [
      {
        key: "model_name",
        header: "Model Name",
        sortable: true,
        render: (item) => (
          <span className="font-medium text-foreground">
            {item.model_name}
          </span>
        ),
      },
      {
        key: "provider",
        header: "Provider",
        render: (item) => (
          <span className="text-sm text-foreground">
            {providerMap[item.provider_id] ?? item.provider_id.slice(0, 8)}
          </span>
        ),
      },
      {
        key: "system_function",
        header: "System Function",
        width: "130px",
        render: (item) => <FunctionBadge fn={item.system_function} />,
      },
      {
        key: "is_active",
        header: "Status",
        width: "90px",
        render: (item) => <StatusBadge active={item.is_active} />,
      },
      {
        key: "health_status",
        header: "Health",
        width: "120px",
        render: (item) => (
          <HealthBadge
            status={item.health_status}
            message={item.health_message}
          />
        ),
      },
      {
        key: "actions",
        header: "",
        width: "140px",
        render: (item) => (
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setEditAssignment(item)}
              className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              aria-label={`Edit ${item.model_name}`}
            >
              <Pencil className="size-3.5" />
            </button>

            <button
              type="button"
              onClick={async () => {
                setPingLoading((prev) => ({
                  ...prev,
                  [item.id]: true,
                }))
                try {
                  await api.pingModelAssignment(item.id)
                } catch {
                  // error ignored — fetchData refreshes the row
                } finally {
                  setPingLoading((prev) => ({
                    ...prev,
                    [item.id]: false,
                  }))
                  fetchData()
                }
              }}
              disabled={pingLoading[item.id]}
              className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-50"
              aria-label={`Ping ${item.model_name}`}
            >
              {pingLoading[item.id] ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <Wifi className="size-3.5" />
              )}
            </button>

            <button
              type="button"
              onClick={async () => {
                try {
                  await api.updateModelAssignment(item.id, {
                    is_active: !item.is_active,
                  })
                  fetchData()
                } catch {
                  // error ignored — fetchData refreshes the row
                }
              }}
              className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              aria-label={
                item.is_active
                  ? `Deactivate ${item.model_name}`
                  : `Activate ${item.model_name}`
              }
            >
              {item.is_active ? (
                <Power className="size-3.5" />
              ) : (
                <PowerOff className="size-3.5" />
              )}
            </button>

            <button
              type="button"
              onClick={() => setDeleteAssignment(item)}
              className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
              aria-label={`Delete ${item.model_name}`}
            >
              <Trash2 className="size-3.5" />
            </button>
          </div>
        ),
      },
    ],
    [providerMap, pingLoading, fetchData],
  )

  return (
    <div data-slot="assignment-manager" className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-foreground">
            Model Assignments
          </h2>
          <p className="text-sm text-muted-foreground">
            Assign models to system functions (retrieval, generation,
            evaluation)
          </p>
        </div>
        <Button onClick={() => setAddOpen(true)}>
          <Plus className="size-4" />
          Add Assignment
        </Button>
      </div>

      <DataTable<ModelAssignmentResponse>
        data={sortedAssignments}
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
        emptyMessage="No assignments configured. Add one to get started."
        sortKey={sortKey}
        sortDir={sortDir}
        onSort={(key, dir) => {
          setSortKey(key)
          setSortDir(dir)
        }}
      />

      <AddAssignmentDialog
        open={addOpen}
        onOpenChange={setAddOpen}
        onCreated={() => {
          setAddOpen(false)
          fetchData()
        }}
      />

      <EditAssignmentDialog
        assignment={editAssignment}
        open={editAssignment !== null}
        onOpenChange={(open) => {
          if (!open) setEditAssignment(null)
        }}
        onUpdated={() => {
          setEditAssignment(null)
          fetchData()
        }}
        allProviders={allProviders}
      />

      <DeleteAssignmentDialog
        assignment={deleteAssignment}
        open={deleteAssignment !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteAssignment(null)
        }}
        onDeleted={() => {
          setDeleteAssignment(null)
          fetchData()
        }}
      />
    </div>
  )
}
