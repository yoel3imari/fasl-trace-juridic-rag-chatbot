"use client";

import { useCallback, useMemo } from "react";
import dynamic from "next/dynamic";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable";
import { useChatStore } from "@/store/useChatStore";
import { ChatPane } from "@/components/features/chat/ChatPane";
import { WorkspaceToolbar } from "@/components/features/workspace/WorkspaceToolbar";

const DocumentPane = dynamic(
  () =>
    import("@/components/features/document/DocumentPane").then(
      (mod) => mod.DocumentPane
    ),
  {
    ssr: false,
    loading: () => (
      <div className="flex items-center justify-center h-full bg-zinc-100">
        <div className="text-zinc-400 text-sm">Loading document viewer...</div>
      </div>
    ),
  }
);

export function WorkspaceLayout() {
  const panelRatio = useChatStore((s) => s.workspace.panelRatio);
  const setPanelRatio = useChatStore((s) => s.setPanelRatio);

  const handleLayoutChange = useCallback(
    (layout: Record<string, number>) => {
      const chatSize = layout.chat;
      const docSize = layout.document;
      if (chatSize !== undefined && docSize !== undefined) {
        setPanelRatio([chatSize, docSize]);
      }
    },
    [setPanelRatio]
  );

  const [chatSize, docSize] = useMemo(
    (): [number, number] => [panelRatio[0], panelRatio[1]],
    [panelRatio]
  );

  return (
    <div className="h-screen w-screen overflow-hidden flex flex-col">
      <WorkspaceToolbar />
      <ResizablePanelGroup
        orientation="horizontal"
        onLayoutChange={handleLayoutChange}
        className="flex-1 h-full w-full"
      >
        <ResizablePanel
          id="chat"
          defaultSize={chatSize}
          minSize="480px"
          className="bg-slate-900"
        >
          <ChatPane />
        </ResizablePanel>

        <ResizableHandle
          withHandle
          className="w-1 bg-slate-700 hover:bg-blue-500 focus-visible:bg-blue-500 focus-visible:outline-none transition-colors"
        />

        <ResizablePanel
          id="document"
          defaultSize={docSize}
          minSize="480px"
          className="bg-zinc-100"
        >
          <DocumentPane />
        </ResizablePanel>
      </ResizablePanelGroup>
    </div>
  );
}
