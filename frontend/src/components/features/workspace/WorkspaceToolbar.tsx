"use client";

import { RotateCcw } from "lucide-react";
import { useChatStore } from "@/store/useChatStore";
import { CollectionSelector } from "./CollectionSelector";

export function WorkspaceToolbar() {
  const clearSession = useChatStore((s) => s.clearSession);

  return (
    <div className="h-11 bg-slate-900 border-b border-slate-800 px-3 flex items-center justify-between gap-4 shrink-0">
      <span className="text-xs text-slate-400 font-medium tracking-wide select-none">
        Fasl Trace
      </span>

      <div className="flex-1 flex justify-center">
        <CollectionSelector />
      </div>

      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={clearSession}
          className="inline-flex items-center gap-1 px-2 py-1 text-xs text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 rounded transition-colors"
          title="New session"
        >
          <RotateCcw className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">New Session</span>
        </button>
      </div>
    </div>
  );
}
