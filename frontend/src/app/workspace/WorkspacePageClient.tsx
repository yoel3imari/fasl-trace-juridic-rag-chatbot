"use client";

import { AuthGuard } from "@/components/auth/AuthGuard";
import { WorkspaceLayout } from "@/components/features/workspace";
import { DirectionalLayoutSwitcher } from "@/components/features/workspace/DirectionalLayoutSwitcher";

export function WorkspacePageClient() {
  return (
    <AuthGuard>
      <DirectionalLayoutSwitcher>
        <WorkspaceLayout />
      </DirectionalLayoutSwitcher>
    </AuthGuard>
  );
}
