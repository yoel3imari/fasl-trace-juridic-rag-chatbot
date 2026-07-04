"use client";

import { useChatStore } from "@/store/useChatStore";

export function ProcessingStepIndicator() {
  const steps = useChatStore((s) => s.workspace.processingSteps);
  const streamingStatus = useChatStore((s) => s.workspace.streamingStatus);

  if (!steps.length) return null;

  const allComplete = steps.every((s) => s.status === "complete");

  return (
    <div className="px-4 py-2 border-b border-slate-800 font-mono text-xs text-slate-400 flex items-center gap-3 flex-wrap">
      {steps.map((step) => {
        const isComplete = step.status === "complete";
        const isActive = step.status === "active";

        return (
          <span key={step.id} className="inline-flex items-center gap-1">
            {isComplete ? (
              <span className="text-emerald-400">[✓]</span>
            ) : isActive ? (
              <span className="text-cyan-400 animate-pulse">[...]</span>
            ) : (
              <span className="text-slate-600">[   ]</span>
            )}
            <span className={isComplete ? "text-slate-300" : "text-slate-500"}>
              {step.label}
            </span>
          </span>
        );
      })}
      {allComplete && streamingStatus === "streaming" && (
        <span className="text-slate-600">— auto-hiding soon</span>
      )}
    </div>
  );
}
