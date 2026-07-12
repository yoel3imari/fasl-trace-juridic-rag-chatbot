"use client"

import { Clock, Loader2, CheckCircle, XCircle } from "lucide-react"

import { cn } from "@/lib/utils"

const statusConfig: Record<string, { icon: React.ReactNode; className: string; pulse?: boolean }> = {
  pending: {
    icon: <Clock className="size-3" />,
    className: "bg-amber-500/10 text-amber-500",
  },
  processing: {
    icon: <Loader2 className="size-3 animate-spin" />,
    className: "bg-cyan-500/10 text-cyan-500",
    pulse: true,
  },
  processed: {
    icon: <CheckCircle className="size-3" />,
    className: "bg-emerald-500/10 text-emerald-500",
  },
  failed: {
    icon: <XCircle className="size-3" />,
    className: "bg-rose-500/10 text-rose-500",
  },
}

function IngestionStatusBadge({ status }: { status: string }) {
  const config = statusConfig[status.toLowerCase()] ?? statusConfig.pending

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium leading-none",
        config.className,
        config.pulse && "animate-pulse",
      )}
    >
      {config.icon}
      {status.charAt(0).toUpperCase() + status.slice(1).toLowerCase()}
    </span>
  )
}

export { IngestionStatusBadge }
