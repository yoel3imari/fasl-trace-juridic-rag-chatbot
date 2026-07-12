"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import {
  Plus,
  Trash2,
  Key,
  Eye,
  EyeOff,
  X,
  Loader2,
  AlertTriangle,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import { DataTable, type Column } from "@/components/ui/data-table/DataTable"
import { api } from "@/lib/data"
import type { LlmProviderResponse, ApiKeyResponse } from "@/lib/data"
import { cn } from "@/lib/utils"

const PROVIDER_LABELS: Record<string, string> = {
  openai: "OpenAI",
  anthropic: "Anthropic",
  ollama: "Ollama",
}

const DEFAULT_URLS: Record<string, string> = {
  openai: "https://api.openai.com/v1",
  anthropic: "https://api.anthropic.com",
  ollama: "http://localhost:11434",
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

function ApiKeyBadge({ hasKey }: { hasKey: boolean }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium leading-none",
        hasKey
          ? "bg-emerald-500/10 text-emerald-500"
          : "bg-amber-500/10 text-amber-500",
      )}
    >
      {hasKey ? "Key set" : "No key"}
    </span>
  )
}

/* ------------------------------------------------------------------ */
/*  API Key Dialog                                                     */
/* ------------------------------------------------------------------ */

interface ApiKeyDialogProps {
  provider: LlmProviderResponse
  open: boolean
  onOpenChange: (open: boolean) => void
  onUpdated: () => void
}

function ApiKeyDialog({
  provider,
  open,
  onOpenChange,
  onUpdated,
}: ApiKeyDialogProps) {
  const [apiKey, setApiKey] = useState("")
  const [showKey, setShowKey] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [keyStatus, setKeyStatus] = useState<ApiKeyResponse | null>(null)
  const [loadingStatus, setLoadingStatus] = useState(true)

  useEffect(() => {
    if (!open) return
    setApiKey("")
    setShowKey(false)
    setError(null)
    setKeyStatus(null)
    setLoadingStatus(true)

    api
      .getProviderApiKeyStatus(provider.id)
      .then(setKeyStatus)
      .catch((err: unknown) =>
        setError(
          err instanceof Error ? err.message : "Failed to load key status",
        ),
      )
      .finally(() => setLoadingStatus(false))
  }, [open, provider.id])

  const handleSet = async () => {
    const trimmed = apiKey.trim()
    if (!trimmed) return

    setSubmitting(true)
    setError(null)

    try {
      const result = await api.setProviderApiKey(provider.id, {
        api_key: trimmed,
      })
      setKeyStatus(result)
      setApiKey("")
      onUpdated()
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to set API key",
      )
    } finally {
      setSubmitting(false)
    }
  }

  const handleDelete = async () => {
    setDeleting(true)
    setError(null)

    try {
      const result = await api.deleteProviderApiKey(provider.id)
      setKeyStatus(result)
      onUpdated()
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to delete API key",
      )
    } finally {
      setDeleting(false)
    }
  }

  const handleClose = () => {
    if (submitting || deleting) return
    setApiKey("")
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
        aria-labelledby="apikey-dialog-title"
        className={cn(
          "relative z-10 w-full max-w-md rounded-xl border border-border",
          "bg-background p-6 shadow-2xl",
          "animate-in fade-in zoom-in-95 duration-200",
        )}
      >
        <div className="mb-5 flex items-center justify-between">
          <h2
            id="apikey-dialog-title"
            className="text-base font-semibold text-foreground"
          >
            API Key{" "}
            <span className="text-muted-foreground font-normal">
              &mdash;{" "}
              {PROVIDER_LABELS[provider.provider_type] ??
                provider.provider_type}
            </span>
          </h2>
          <button
            type="button"
            onClick={handleClose}
            disabled={submitting || deleting}
            className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-50"
            aria-label="Close"
          >
            <X className="size-4" />
          </button>
        </div>

        <div className="flex flex-col gap-4">
          <div className="rounded-md bg-muted px-3 py-2.5">
            <div className="mb-1 text-xs text-muted-foreground">
              Current status
            </div>
            {loadingStatus ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="size-3.5 animate-spin" />
                Loading...
              </div>
            ) : (
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <ApiKeyBadge hasKey={keyStatus?.has_api_key ?? false} />
                  {keyStatus?.masked_key && (
                    <span className="font-mono text-xs text-muted-foreground">
                      {keyStatus.masked_key}
                    </span>
                  )}
                </div>
                {keyStatus?.updated_at && (
                  <span className="text-[10px] text-muted-foreground">
                    Updated{" "}
                    {new Date(keyStatus.updated_at).toLocaleDateString()}
                  </span>
                )}
              </div>
            )}
          </div>

          <div className="flex flex-col gap-1.5">
            <label
              htmlFor="api-key-input"
              className="text-sm font-medium text-foreground"
            >
              {keyStatus?.has_api_key ? "Update API Key" : "Set API Key"}
            </label>
            <div className="relative">
              <input
                id="api-key-input"
                type={showKey ? "text" : "password"}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={
                  provider.provider_type === "openai"
                    ? "sk-proj-..."
                    : provider.provider_type === "anthropic"
                      ? "sk-ant-..."
                      : "Enter API key"
                }
                disabled={submitting || deleting}
                autoFocus
                className={cn(
                  "h-9 w-full rounded-md border border-input bg-muted px-3 pr-9 text-sm text-foreground",
                  "outline-none transition-colors",
                  "placeholder:text-muted-foreground/60",
                  "focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30",
                  "disabled:opacity-50",
                )}
              />
              <button
                type="button"
                onClick={() => setShowKey(!showKey)}
                disabled={submitting || deleting}
                className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-0.5 text-muted-foreground transition-colors hover:text-foreground disabled:opacity-50"
                aria-label={showKey ? "Hide key" : "Show key"}
              >
                {showKey ? (
                  <EyeOff className="size-3.5" />
                ) : (
                  <Eye className="size-3.5" />
                )}
              </button>
            </div>
          </div>

          {error && (
            <div className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error}
            </div>
          )}

          <div className="flex items-center justify-between gap-2 pt-1">
            <div>
              {keyStatus?.has_api_key && (
                <Button
                  type="button"
                  variant="destructive"
                  size="sm"
                  disabled={submitting || deleting}
                  onClick={handleDelete}
                >
                  {deleting && (
                    <Loader2 className="size-3.5 animate-spin" />
                  )}
                  {deleting ? "Deleting..." : "Delete Key"}
                </Button>
              )}
            </div>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={submitting || deleting}
                onClick={handleClose}
              >
                Cancel
              </Button>
              <Button
                type="button"
                size="sm"
                disabled={submitting || deleting || !apiKey.trim()}
                onClick={handleSet}
              >
                {submitting && (
                  <Loader2 className="size-3.5 animate-spin" />
                )}
                {submitting ? "Setting..." : "Set Key"}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Add Provider Dialog                                                */
/* ------------------------------------------------------------------ */

interface AddProviderDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreated: () => void
}

function AddProviderDialog({
  open,
  onOpenChange,
  onCreated,
}: AddProviderDialogProps) {
  const [providerType, setProviderType] = useState<
    "openai" | "anthropic" | "ollama" | ""
  >("")
  const [baseUrl, setBaseUrl] = useState("")
  const [apiVersion, setApiVersion] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    setProviderType("")
    setBaseUrl("")
    setApiVersion("")
    setError(null)
  }, [open])

  const handleProviderTypeChange = (type: string) => {
    setProviderType(type as "openai" | "anthropic" | "ollama")
    setBaseUrl(DEFAULT_URLS[type] ?? "")
    if (type === "ollama") {
      setApiVersion("")
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!providerType) return

    setSubmitting(true)
    setError(null)

    try {
      await api.createLlmProvider({
        provider_type: providerType,
        base_url: baseUrl || undefined,
        api_version: apiVersion || undefined,
      })
      onCreated()
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to create provider",
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
        aria-labelledby="add-provider-dialog-title"
        className={cn(
          "relative z-10 w-full max-w-md rounded-xl border border-border",
          "bg-background p-6 shadow-2xl",
          "animate-in fade-in zoom-in-95 duration-200",
        )}
      >
        <div className="mb-5 flex items-center justify-between">
          <h2
            id="add-provider-dialog-title"
            className="text-base font-semibold text-foreground"
          >
            Add Provider
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
              htmlFor="provider-type"
              className="text-sm font-medium text-foreground"
            >
              Provider Type
            </label>
            <select
              id="provider-type"
              value={providerType}
              onChange={(e) => handleProviderTypeChange(e.target.value)}
              required
              disabled={submitting}
              autoFocus
              className="h-9 rounded-md border border-input bg-muted px-3 text-sm text-foreground outline-none transition-colors focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30 disabled:opacity-50"
            >
              <option value="">Select provider...</option>
              <option value="openai">OpenAI</option>
              <option value="anthropic">Anthropic</option>
              <option value="ollama">Ollama</option>
            </select>
          </div>

          <div className="flex flex-col gap-1.5">
            <label
              htmlFor="provider-base-url"
              className="text-sm font-medium text-foreground"
            >
              Base URL{" "}
              <span className="font-normal text-muted-foreground">
                (optional)
              </span>
            </label>
            <input
              id="provider-base-url"
              type="text"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder={
                providerType ? DEFAULT_URLS[providerType] : "https://..."
              }
              disabled={submitting}
              className="h-9 rounded-md border border-input bg-muted px-3 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground/60 focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30 disabled:opacity-50"
            />
          </div>

          {providerType !== "ollama" && (
            <div className="flex flex-col gap-1.5">
              <label
                htmlFor="provider-api-version"
                className="text-sm font-medium text-foreground"
              >
                API Version{" "}
                <span className="font-normal text-muted-foreground">
                  (optional)
                </span>
              </label>
              <input
                id="provider-api-version"
                type="text"
                value={apiVersion}
                onChange={(e) => setApiVersion(e.target.value)}
                placeholder={
                  providerType === "anthropic" ? "2023-06-01" : "v1"
                }
                disabled={submitting}
                className="h-9 rounded-md border border-input bg-muted px-3 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground/60 focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30 disabled:opacity-50"
              />
            </div>
          )}

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
              disabled={submitting || !providerType}
            >
              {submitting && (
                <Loader2 className="size-3.5 animate-spin" />
              )}
              {submitting ? "Adding..." : "Add Provider"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Delete Provider Dialog                                             */
/* ------------------------------------------------------------------ */

interface DeleteProviderDialogProps {
  provider: LlmProviderResponse | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onDeleted: () => void
}

function DeleteProviderDialog({
  provider,
  open,
  onOpenChange,
  onDeleted,
}: DeleteProviderDialogProps) {
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleConfirm = async () => {
    if (!provider) return

    setSubmitting(true)
    setError(null)

    try {
      await api.deleteLlmProvider(provider.id)
      onDeleted()
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to delete provider",
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

  if (!open || !provider) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={handleClose}
      />

      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="delete-provider-dialog-title"
        aria-describedby="delete-provider-dialog-desc"
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
                id="delete-provider-dialog-title"
                className="text-base font-semibold text-foreground"
              >
                Delete Provider
              </h2>
              <p
                id="delete-provider-dialog-desc"
                className="mt-0.5 text-sm text-muted-foreground"
              >
                Are you sure you want to delete{" "}
                <span className="font-medium text-foreground">
                  {PROVIDER_LABELS[provider.provider_type] ??
                    provider.provider_type}
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
          This action cannot be undone. Any model assignments using this
          provider will also be removed.
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
/*  ProviderManager                                                    */
/* ------------------------------------------------------------------ */

export function ProviderManager() {
  const [providers, setProviders] = useState<LlmProviderResponse[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(100)

  const [addOpen, setAddOpen] = useState(false)
  const [apiKeyProvider, setApiKeyProvider] =
    useState<LlmProviderResponse | null>(null)
  const [deleteProvider, setDeleteProvider] =
    useState<LlmProviderResponse | null>(null)
  const [sortKey, setSortKey] = useState<string | undefined>("updated_at")
  const [sortDir, setSortDir] = useState<"asc" | "desc" | undefined>("desc")

  const fetchProviders = useCallback(async () => {
    setLoading(true)
    try {
      const skip = (page - 1) * pageSize
      const result = await api.listLlmProviders({ skip, limit: pageSize })
      setProviders(result.items)
      setTotal(result.total)
    } catch {
      setProviders([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }, [page, pageSize])

  useEffect(() => {
    fetchProviders()
  }, [fetchProviders])

  const sortedProviders = useMemo(() => {
    if (!sortKey || !sortDir) return providers
    return [...providers].sort((a, b) => {
      let aVal: string | number = ""
      let bVal: string | number = ""

      if (sortKey === "updated_at" || sortKey === "created_at") {
        aVal = new Date(a[sortKey] ?? a.created_at).getTime()
        bVal = new Date(b[sortKey] ?? b.created_at).getTime()
      } else if (sortKey === "provider_type") {
        aVal = a.provider_type.toLowerCase()
        bVal = b.provider_type.toLowerCase()
      }

      if (aVal < bVal) return sortDir === "asc" ? -1 : 1
      if (aVal > bVal) return sortDir === "asc" ? 1 : -1
      return 0
    })
  }, [providers, sortKey, sortDir])

  const columns: Column<LlmProviderResponse>[] = useMemo(
    () => [
      {
        key: "provider_type",
        header: "Provider Type",
        sortable: true,
        render: (item) => (
          <span className="font-medium text-foreground">
            {PROVIDER_LABELS[item.provider_type] ?? item.provider_type}
          </span>
        ),
      },
      {
        key: "base_url",
        header: "Base URL",
        render: (item) => (
          <span
            className={cn(
              "text-sm",
              item.base_url ? "text-foreground" : "italic text-muted-foreground",
            )}
          >
            {item.base_url ?? "Default"}
          </span>
        ),
      },
      {
        key: "is_active",
        header: "Status",
        width: "90px",
        render: (item) => <StatusBadge active={item.is_active} />,
      },
      {
        key: "has_api_key",
        header: "API Key",
        width: "80px",
        render: (item) => (
          <ApiKeyBadge hasKey={item.has_api_key ?? false} />
        ),
      },
      {
        key: "warning",
        header: "Warning",
        render: (item) =>
          item.warning ? (
            <span className="flex items-center gap-1.5 text-xs text-amber-500">
              <AlertTriangle className="size-3 shrink-0" />
              {item.warning}
            </span>
          ) : (
            <span className="text-muted-foreground">&mdash;</span>
          ),
      },
      {
        key: "actions",
        header: "",
        width: "90px",
        render: (item) => (
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setApiKeyProvider(item)}
              className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              aria-label={`Manage API key for ${item.provider_type}`}
            >
              <Key className="size-3.5" />
            </button>
            <button
              type="button"
              onClick={() => setDeleteProvider(item)}
              className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
              aria-label={`Delete ${item.provider_type} provider`}
            >
              <Trash2 className="size-3.5" />
            </button>
          </div>
        ),
      },
    ],
    [],
  )

  return (
    <div data-slot="provider-manager" className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-foreground">
            LLM Providers
          </h2>
          <p className="text-sm text-muted-foreground">
            Manage AI service providers and their API keys
          </p>
        </div>
        <Button onClick={() => setAddOpen(true)}>
          <Plus className="size-4" />
          Add Provider
        </Button>
      </div>

      <DataTable<LlmProviderResponse>
        data={sortedProviders}
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
        emptyMessage="No providers configured. Add one to get started."
        sortKey={sortKey}
        sortDir={sortDir}
        onSort={(key, dir) => {
          setSortKey(key)
          setSortDir(dir)
        }}
      />

      <AddProviderDialog
        open={addOpen}
        onOpenChange={setAddOpen}
        onCreated={() => {
          setAddOpen(false)
          fetchProviders()
        }}
      />

      {apiKeyProvider && (
        <ApiKeyDialog
          provider={apiKeyProvider}
          open
          onOpenChange={(open) => {
            if (!open) setApiKeyProvider(null)
          }}
          onUpdated={() => {
            fetchProviders()
          }}
        />
      )}

      <DeleteProviderDialog
        provider={deleteProvider}
        open={deleteProvider !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteProvider(null)
        }}
        onDeleted={() => {
          setDeleteProvider(null)
          fetchProviders()
        }}
      />
    </div>
  )
}
