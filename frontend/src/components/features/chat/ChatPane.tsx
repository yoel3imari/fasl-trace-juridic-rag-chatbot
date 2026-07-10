"use client";

import { ScrollArea } from "@/components/ui/scroll-area";
import { ChatInput } from "@/components/features/chat/ChatInput";
import { MessageList } from "@/components/features/chat/MessageList";
import { ProcessingStepIndicator } from "@/components/features/chat/ProcessingStepIndicator";
import { useChatStore } from "@/store/useChatStore";
import { MessageSquare } from "lucide-react";

function WelcomePlaceholder() {
  return (
    <div className="flex flex-col items-center justify-center h-full px-8 text-center gap-4">
      <div className="rounded-full bg-slate-800 p-4">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="32"
          height="32"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="text-slate-400"
        >
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
      </div>
      <h2 className="text-xl font-semibold text-slate-50">Welcome to Fasl Trace</h2>
      <p className="text-sm text-slate-400 max-w-sm leading-relaxed">
        Select a document collection to begin analysis. Ask questions about your
        documents and get answers with legal citations back to the source.
      </p>
    </div>
  );
}

export function ChatPane() {
  const { sessionId, messages, selectedDocumentId } = useChatStore((s) => ({
    sessionId: s.workspace.sessionId,
    messages: s.workspace.messages,
    selectedDocumentId: s.workspace.selectedDocumentId,
  }));
  const hasMessages = messages.length > 0;

  return (
    <div className="flex flex-col h-full text-slate-50 text-start">
      {/* Session metadata header */}
      <div className="border-b border-slate-700 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm text-slate-300">
          <MessageSquare className="w-4 h-4" />
          <span>
            {sessionId
              ? `Session ${sessionId.slice(0, 8)}...`
              : "No active session"}
          </span>
          {selectedDocumentId && (
            <span className="text-slate-500">• {selectedDocumentId}</span>
          )}
        </div>
        <div className="text-xs text-slate-400">
          {messages.length} message{messages.length !== 1 ? "s" : ""}
        </div>
      </div>
      <div className="flex-none">
        <ProcessingStepIndicator />
      </div>
      <ScrollArea className="flex-1 px-4 py-3">
        {hasMessages ? (
          <MessageList />
        ) : (
          <WelcomePlaceholder />
        )}
      </ScrollArea>
      <div className="border-t border-slate-800 px-4 py-3">
        <ChatInput />
      </div>
    </div>
  );
}
