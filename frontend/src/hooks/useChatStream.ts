"use client";

import { useCallback, useRef } from "react";
import { useChatStore } from "@/store/useChatStore";
import { createClient } from "@/lib/supabase";
import type { Citation } from "@/store/useChatStore";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function useChatStream() {
  const appendToken = useChatStore((s) => s.appendToken);
  const setMessageCitations = useChatStore((s) => s.setMessageCitations);
  const updateProcessingStep = useChatStore((s) => s.updateProcessingStep);
  const setProcessingSteps = useChatStore((s) => s.setProcessingSteps);
  const setStreamError = useChatStore((s) => s.setStreamError);
  const finalizeMessage = useChatStore((s) => s.finalizeMessage);
  const setStreamingStatus = useChatStore((s) => s.setStreamingStatus);
  const getCurrentStreamingMessageId = useChatStore((s) => s.getCurrentStreamingMessageId);

  const abortRef = useRef<() => void>(() => {});

  const onEvent = useCallback(
    (type: string, data: Record<string, unknown>) => {
      const messageId = getCurrentStreamingMessageId();
      if (!messageId) return;

      switch (type) {
        case "token": {
          const content = typeof data.content === "string" ? data.content : "";
          if (content) appendToken(messageId, content);
          break;
        }
        case "citation": {
          const citations = Array.isArray(data.citations) ? data.citations : [];
          setMessageCitations(messageId, citations as Citation[]);
          break;
        }
        case "processing_step": {
          const step = typeof data.step === "string" ? data.step : "";
          const status = typeof data.status === "string" ? data.status : "";
          if (step && status) {
            updateProcessingStep(step, status as "pending" | "active" | "complete");
            if (step === "retrieval" && status === "active") {
              setProcessingSteps([
                { id: "retrieval", label: "Retrieval", status: "active" },
                { id: "generation", label: "Generation", status: "pending" },
              ]);
            }
          }
          break;
        }
        case "error": {
          const content = typeof data.content === "string" ? data.content : "";
          if (content) setStreamError(messageId, content);
          break;
        }
        case "warning": {
          const content = typeof data.content === "string" ? data.content : "";
          if (content) {
            useChatStore.getState().addMessage({
              id: `msg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
              role: "system",
              content: `Warning: ${content}`,
              timestamp: new Date().toISOString(),
            });
          }
          break;
        }
        case "done": {
          finalizeMessage(messageId);
          break;
        }
        default:
          break;
      }
    },
    [
      appendToken,
      setMessageCitations,
      updateProcessingStep,
      setProcessingSteps,
      setStreamError,
      finalizeMessage,
      getCurrentStreamingMessageId,
    ]
  );

  const onDone = useCallback(() => {
    setStreamingStatus("complete");
  }, [setStreamingStatus]);

  const onError = useCallback(
    (message: string) => {
      const messageId = getCurrentStreamingMessageId();
      if (messageId) setStreamError(messageId, message);
      setStreamingStatus("error");
    },
    [getCurrentStreamingMessageId, setStreamError, setStreamingStatus]
  );

  const startStream = useCallback(
    async (query: string, collectionId?: string) => {
      abortRef.current?.();

      const supabase = createClient();
      const {
        data: { session },
      } = await supabase.auth.getSession();

      const accessToken = session?.access_token;
      if (!accessToken) {
        const messageId = getCurrentStreamingMessageId();
        if (messageId) setStreamError(messageId, "No active session. Please sign in.");
        setStreamingStatus("error");
        return;
      }

      const url = `${API_URL}/api/v1/chat/stream`;
      const body = { query, collection_id: collectionId };

      const controller = new AbortController();
      abortRef.current = () => controller.abort();

      setStreamingStatus("processing");

      try {
        const response = await fetch(url, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${accessToken}`,
          },
          body: JSON.stringify(body),
          signal: controller.signal,
        });

        if (!response.ok) {
          const text = await response.text().catch(() => "");
          throw new Error(`Server returned ${response.status}: ${text.slice(0, 200)}`);
        }

        setStreamingStatus("streaming");

        const reader = response.body?.getReader();
        if (!reader) throw new Error("Response body is not readable");

        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          const parts = buffer.split("\n\n");
          buffer = parts.pop() || "";

          for (const part of parts) {
            const lines = part.split("\n");
            for (const line of lines) {
              const trimmed = line.trim();
              if (!trimmed.startsWith("data:")) continue;

              const jsonStr = trimmed.slice(5).trim();
              if (jsonStr === "[DONE]" || jsonStr === "done") {
                onDone?.();
                return;
              }

              try {
                const data = JSON.parse(jsonStr) as Record<string, unknown>;
                const type = typeof data.type === "string" ? data.type : "unknown";
                onEvent(type, data);
              } catch {
                // skip non-JSON lines
              }
            }
          }
        }

        onDone?.();
      } catch (err: unknown) {
        if ((err as Error).name === "AbortError") return;
        const msg = err instanceof Error ? err.message : String(err);
        onError(msg);
      }
    },
    [
      getCurrentStreamingMessageId,
      setStreamError,
      setStreamingStatus,
      onEvent,
      onDone,
      onError,
    ]
  );

  const abort = useCallback(() => {
    abortRef.current?.();
    setStreamingStatus("idle");
  }, [setStreamingStatus]);

  return { startStream, abort };
}