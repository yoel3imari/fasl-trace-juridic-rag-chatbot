"use client";

import { useState, useEffect, useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { Button } from "@/components/ui/button";
import { ArrowDown } from "lucide-react";
import { useChatStore } from "@/store/useChatStore";
import { MessageBubble } from "./MessageBubble";

export function MessageList() {
  const messages = useChatStore((s) => s.getMessages());
  const streamingStatus = useChatStore((s) => s.workspace.streamingStatus);
  const direction = useChatStore((s) => s.workspace.direction);

  const [isUserAtBottom, setIsUserAtBottom] = useState(true);
  const [showHistoryBadge, setShowHistoryBadge] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);

  const virtualizer = useVirtualizer({
    getScrollElement: () => containerRef.current?.parentElement ?? null,
    count: messages.length,
    estimateSize: (index) => {
      const msg = messages[index];
      if (!msg) return 120;
      const base = 60;
      const charHeight = 1.2;
      const estimatedContent = Math.min(msg.content.length * charHeight, 400);
      return Math.max(base + estimatedContent, 80);
    },
    overscan: 5,
  });

  const handleScrollRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    const viewport = containerRef.current?.parentElement;
    if (!viewport) return;

    handleScrollRef.current = () => {
      const threshold = 50;
      const atBottom =
        viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight < threshold;
      setIsUserAtBottom(atBottom);

      const atTop = viewport.scrollTop < threshold;
      setShowHistoryBadge(atTop && messages.length > 0);
    };

    const handler = () => handleScrollRef.current?.();
    viewport.addEventListener("scroll", handler, { passive: true });
    return () => viewport.removeEventListener("scroll", handler);
  }, []);

  useEffect(() => {
    if (messages.length === 0) return;
    if (!isUserAtBottom) return;

    virtualizer.scrollToIndex(messages.length - 1, { align: "end" });
  }, [messages.length, isUserAtBottom]);

  const handleScrollToBottom = () => {
    virtualizer.scrollToIndex(messages.length - 1, { align: "end" });
    setIsUserAtBottom(true);
  };

  if (messages.length === 0) {
    return (
      <div ref={containerRef} className="flex items-center justify-center h-full text-slate-500 text-sm">
        No messages yet. Start a conversation!
      </div>
    );
  }

  return (
    <div ref={containerRef} className="relative">
      {/* History badge — shown when scrolled to top */}
      {showHistoryBadge && (
        <div className="sticky top-0 z-10 flex justify-center py-2">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs bg-slate-700 text-slate-300">
            Viewing session history &middot; {messages.length} message{messages.length !== 1 ? "s" : ""}
          </span>
        </div>
      )}

      <div
        style={{
          height: `${virtualizer.getTotalSize()}px`,
          position: "relative",
        }}
      >
        {virtualizer.getVirtualItems().map((virtualItem) => {
          const message = messages[virtualItem.index];
          if (!message) return null;
          return (
            <div
              key={message.id}
              data-index={virtualItem.index}
              ref={virtualizer.measureElement}
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                width: "100%",
                transform: `translateY(${virtualItem.start}px)`,
              }}
            >
              <MessageBubble message={message} direction={direction} />
            </div>
          );
        })}
      </div>

      {/* Scroll to Bottom button — shown when user has scrolled up */}
      {!isUserAtBottom && (
        <div className="sticky bottom-4 flex justify-center z-10">
          <Button
            size="sm"
            variant="secondary"
            className="rounded-full shadow-lg gap-1.5"
            onClick={handleScrollToBottom}
          >
            <ArrowDown className="w-3.5 h-3.5" />
            Bottom
          </Button>
        </div>
      )}
    </div>
  );
}
