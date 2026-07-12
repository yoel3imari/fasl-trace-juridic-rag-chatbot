"use client";

import { WorkspaceLayout } from "@/components/features/workspace";
import { DirectionalLayoutSwitcher } from "@/components/features/workspace/DirectionalLayoutSwitcher";

export function WorkspacePageClient() {
  return (
    <DirectionalLayoutSwitcher>
      <WorkspaceLayout />
    </DirectionalLayoutSwitcher>
  );
}
