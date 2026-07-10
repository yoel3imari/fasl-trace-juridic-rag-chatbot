"use client";

import { useState, useRef, useEffect } from "react";
import { Textarea } from "@/components/ui/textarea";
import { useChatStore } from "@/store/useChatStore";
import { useChatStream } from "@/hooks/useChatStream";

const MAX_ROWS = 6;
const ENTER_KEY = "Enter";
const MODIFIER_KEYS = ["Meta", "Control"];

export function ChatInput() {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const addUserMessage = useChatStore((s) => s.addUserMessage);
  const startAssistantMessage = useChatStore((s) => s.startAssistantMessage);
  const streamingStatus = useChatStore((s) => s.workspace.streamingStatus);
  const { startStream } = useChatStream();

  const isDisabled = streamingStatus !== "idle";

  const submit = () => {
    const trimmed = value.trim();
    if (!trimmed) return;
    setValue("");
    addUserMessage(trimmed);
    startAssistantMessage();
    startStream(trimmed, undefined);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === ENTER_KEY && !e.shiftKey) {
      e.preventDefault();
      submit();
    } else if (
      e.key === ENTER_KEY &&
      (e.metaKey || e.ctrlKey)
    ) {
      e.preventDefault();
      submit();
    }
  };

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    const maxHeight = MAX_ROWS * 24;
    el.style.height = `${Math.min(el.scrollHeight, maxHeight)}px`;
  }, [value]);

  return (
    <div className="relative">
      <Textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={
          isDisabled
            ? "Processing..."
            : "Ask a question about your documents..."
        }
        className="min-h-[48px] max-h-[144px] resize-none bg-slate-950 border-slate-700 text-slate-50 placeholder:text-slate-500 focus-visible:ring-2 focus-visible:ring-cyan-500 focus-visible:border-cyan-500 rounded-lg pe-10"
        rows={1}
        disabled={isDisabled}
      />
      <button
        onClick={submit}
        disabled={isDisabled || !value.trim()}
        className="absolute end-2 bottom-2 p-1.5 rounded-md text-slate-400 hover:text-slate-200 hover:bg-slate-800 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        aria-label="Send message"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M22 2L11 13" />
          <path d="M22 2l-7 20-4-9-9-4 20-7z" />
        </svg>
      </button>
    </div>
  );
}
