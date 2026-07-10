"use client";

import { ChatMessage, useChatStore } from "@/store/useChatStore";
import { formatRelativeTime } from "@/lib/formatRelativeTime";
import { User, MessageSquare, AlertTriangle, AlertCircle } from "lucide-react";

interface MessageBubbleProps {
  message: ChatMessage;
  direction: "ltr" | "rtl";
}

export function MessageBubble({ message, direction }: MessageBubbleProps) {
  const setActiveCitation = useChatStore((s) => s.setActiveCitation);
  const isUser = message.role === "user";
  const isSystem = message.role === "system";

  return (
    <div
      className={`flex ${isUser ? "justify-end" : "justify-start"} mb-3`}
      dir={direction}
    >
      <div
        className={`max-w-[80%] rounded-lg px-4 py-2.5 ${
          isUser
            ? "bg-slate-800 text-slate-50 rounded-br-md"
            : isSystem
              ? "bg-slate-900 text-slate-300 rounded-lg"
              : "bg-slate-700 text-slate-50 rounded-bl-md"
        }`}
      >
        {/* Role header: icon + label */}
        <div
          className={`flex items-center gap-1.5 mb-1 text-xs font-medium ${
            isUser ? "text-slate-400" : isSystem ? "text-slate-500" : "text-cyan-400"
          }`}
        >
          {isUser ? (
            <User className="w-3.5 h-3.5" aria-hidden="true" />
          ) : isSystem ? (
            <MessageSquare className="w-3.5 h-3.5" aria-hidden="true" />
          ) : (
            <MessageSquare className="w-3.5 h-3.5" aria-hidden="true" />
          )}
          <span>{isUser ? "You" : isSystem ? "System" : "Fasl Trace"}</span>
        </div>

        {message.isStreaming && (
          <span className="inline-block w-2 h-4 bg-cyan-500 animate-pulse rounded-sm align-text-bottom ml-1" />
        )}

        {/* Message content */}
        <span className="whitespace-pre-wrap break-words text-start">
          {message.content}
        </span>

        {/* Error banner */}
        {message.error && (
          <div className="mt-2 flex items-start gap-2 rounded-md bg-rose-900/50 border border-rose-700 px-3 py-2">
            <AlertCircle className="w-4 h-4 mt-0.5 shrink-0 text-rose-400" />
            <span className="text-sm text-rose-200">{message.error}</span>
          </div>
        )}

        {/* Warning banner */}
        {message.warning && (
          <div className="mt-2 flex items-start gap-2 rounded-md bg-amber-900/50 border border-amber-700 px-3 py-2">
            <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0 text-amber-400" />
            <span className="text-sm text-amber-200">{message.warning}</span>
          </div>
        )}

        {/* Citation badges */}
        {message.citations?.map((citation, i) => (
          <button
            key={i}
            onClick={() => setActiveCitation(citation)}
            className="inline-block mx-0.5 px-1.5 py-0.5 rounded text-xs bg-slate-600 text-slate-400 cursor-pointer hover:bg-slate-500 hover:text-slate-200 transition-colors"
            data-citation-id={`${message.id}-${i}`}
          >
            [{i + 1}]
          </button>
        ))}

        {/* Timestamp */}
        <div className="mt-1 text-[10px] text-slate-500 text-start">
          {formatRelativeTime(message.timestamp)}
        </div>
      </div>
    </div>
  );
}
