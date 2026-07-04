import { useState, useEffect, useRef, useCallback } from "react";

export type SSEStatus = "idle" | "connecting" | "streaming" | "done" | "error";

interface SSEStreamResult {
  status: SSEStatus;
  error: string | null;
  abort: () => void;
}

/**
 * Open an SSE stream via fetch (POST-compatible).
 * Returns { status, error, abort }.
 * Calls onEvent(type, data) for each parsed SSE event.
 */
export function useSSEStream(
  url: string,
  body: Record<string, unknown>,
  onEvent: (type: string, data: Record<string, unknown>) => void,
  onDone?: () => void,
  onError?: (message: string) => void,
): SSEStreamResult {
  const [status, setStatus] = useState<SSEStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const activeRef = useRef(true);

  useEffect(() => {
    activeRef.current = true;
    return () => {
      activeRef.current = false;
      abortRef.current?.abort();
    };
  }, []);

  const abort = useCallback(() => {
    abortRef.current?.abort();
    if (activeRef.current) {
      setStatus("idle");
    }
  }, []);

  useEffect(() => {
    if (!url) return;

    let cancelled = false;
    const controller = new AbortController();
    abortRef.current = controller;

    const run = async () => {
      setStatus("connecting");
      setError(null);

      try {
        const response = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
          signal: controller.signal,
        });

        if (!response.ok) {
          const text = await response.text().catch(() => "");
          throw new Error(`Server returned ${response.status}: ${text.slice(0, 200)}`);
        }

        setStatus("streaming");

        const reader = response.body?.getReader();
        if (!reader) throw new Error("Response body is not readable");

        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done || cancelled) break;

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
                if (activeRef.current) setStatus("done");
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

        if (!cancelled && activeRef.current) {
          setStatus("done");
          onDone?.();
        }
      } catch (err: unknown) {
        if ((err as Error).name === "AbortError") return;
        const msg = err instanceof Error ? err.message : String(err);
        if (activeRef.current) {
          setError(msg);
          setStatus("error");
          onError?.(msg);
        }
      }
    };

    run();

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [url, JSON.stringify(body)]);

  return { status, error, abort };
}
