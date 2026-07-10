"use client";

import { Component, memo, useCallback, useEffect, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { useChatStore, Citation } from "@/store/useChatStore";

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url
).toString();

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center h-full px-8 text-center gap-3">
      <div className="rounded-full bg-zinc-200 p-4">
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
          className="text-zinc-400"
        >
          <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
          <polyline points="14 2 14 8 20 8" />
        </svg>
      </div>
      <p className="text-sm text-zinc-500 max-w-xs">
        No document selected. Choose a document from your collection to view it
        here.
      </p>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-4 px-8">
      <Skeleton className="h-[500px] w-[400px] max-w-full rounded-lg" />
      <Skeleton className="h-4 w-60 rounded" />
      <p className="text-sm text-zinc-400">Loading document...</p>
    </div>
  );
}

function ErrorState({ error, onRetry }: { error: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-full px-8 text-center gap-3">
      <div className="rounded-full bg-red-100 p-4">
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
          className="text-red-500"
        >
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
      </div>
      <p className="text-sm text-red-600 font-medium">Failed to load document</p>
      <p className="text-xs text-zinc-500 max-w-xs">{error}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-2 px-4 py-1.5 text-sm rounded-md bg-zinc-200 hover:bg-zinc-300 text-zinc-700 transition-colors"
        >
          Retry
        </button>
      )}
    </div>
  );
}

class PageErrorBoundary extends Component<
  { children: React.ReactNode },
  { hasError: boolean }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="w-[400px] max-w-full h-32 flex items-center justify-center rounded-lg border border-dashed border-zinc-300 mb-4">
          <p className="text-sm text-zinc-400">Failed to render this page</p>
        </div>
      );
    }
    return this.props.children;
  }
}

function useWindowWidth() {
  const [width, setWidth] = useState(
    typeof window !== "undefined" ? window.innerWidth : 1024
  );

  useEffect(() => {
    let frameId: number;
    const handleResize = () => {
      cancelAnimationFrame(frameId);
      frameId = requestAnimationFrame(() => setWidth(window.innerWidth));
    };
    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
      cancelAnimationFrame(frameId);
    };
  }, []);

  return width;
}

function DocumentPaneInner() {
  const pdfUrl = useChatStore((s) => s.workspace.pdfUrl);
  const [numPages, setNumPages] = useState<number>(0);
  const [loadError, setLoadError] = useState<string | null>(null);
  const windowWidth = useWindowWidth();
  const pageWidth = Math.min(windowWidth * 0.55, 800);
  const activeCitation: Citation | null = useChatStore((s) => s.activeCitation);
  const setActiveCitation = useChatStore((s) => s.setActiveCitation);
  const scrollRef = useRef<HTMLDivElement>(null);

  const onDocumentLoadSuccess = useCallback(
    ({ numPages: pages }: { numPages: number }) => {
      setNumPages(pages);
      setLoadError(null);
    },
    []
  );

  const onDocumentLoadError = useCallback((error: Error) => {
    setLoadError(error.message || "Failed to load PDF");
  }, []);

  useEffect(() => {
    setNumPages(0);
    setLoadError(null);
  }, [pdfUrl]);

  useEffect(() => {
    return () => {
      setNumPages(0);
      setLoadError(null);
    };
  }, []);

  useEffect(() => {
    if (!activeCitation) return;
    const pageEl = scrollRef.current?.querySelector(
      `[data-page-number="${activeCitation.page}"]`
    );
    pageEl?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [activeCitation]);

  const handleRetry = useCallback(() => {
    setLoadError(null);
    setNumPages(0);
  }, []);

  if (!pdfUrl) {
    return <EmptyState />;
  }

  if (loadError) {
    return <ErrorState error={loadError} onRetry={handleRetry} />;
  }

  return (
    <div
      className="h-full bg-white"
      dir="ltr"
      onClick={() => setActiveCitation(null)}
    >
      <ScrollArea className="h-full">
        <div ref={scrollRef} className="flex flex-col items-center py-4">
          <Document
            file={pdfUrl}
            onLoadSuccess={onDocumentLoadSuccess}
            onLoadError={onDocumentLoadError}
            loading={
              <div className="flex items-center justify-center p-24">
                <LoadingState />
              </div>
            }
            className="flex flex-col items-center"
          >
            {Array.from({ length: numPages }, (_, i) => (
              <PageErrorBoundary key={`page_${i + 1}`}>
                <Page
                  pageNumber={i + 1}
                  renderTextLayer={true}
                  renderAnnotationLayer={false}
                  className="mb-4 shadow-lg"
                  width={pageWidth}
                />
              </PageErrorBoundary>
            ))}
          </Document>
        </div>
      </ScrollArea>
    </div>
  );
}

export const DocumentPane = memo(DocumentPaneInner);
