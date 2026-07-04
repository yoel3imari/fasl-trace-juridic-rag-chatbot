import type { Metadata } from "next";
import { WorkspacePageClient } from "./WorkspacePageClient";

export const metadata: Metadata = {
  title: "Workspace | Fasl Trace",
};

export default function WorkspacePage() {
  return <WorkspacePageClient />;
}
