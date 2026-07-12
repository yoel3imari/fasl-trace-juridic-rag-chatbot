import type { Metadata } from "next";
import { AppShell } from "@/components/layout/AppShell";
import { ProviderManager } from "@/components/features/settings/ProviderManager";
import { AssignmentManager } from "@/components/features/settings/AssignmentManager";

export const metadata: Metadata = {
  title: "Settings | Fasl Trace",
};

export default function SettingsPage() {
  return (
    <AppShell>
      <div className="flex flex-col gap-8 p-6 max-w-7xl mx-auto w-full">
        <div>
          <h1 className="text-2xl font-semibold text-foreground tracking-tight">
            Settings
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Configure LLM providers and assign models to system functions.
          </p>
        </div>
        <section aria-label="LLM Providers">
          <ProviderManager />
        </section>
        <section aria-label="Model Assignments">
          <AssignmentManager />
        </section>
      </div>
    </AppShell>
  );
}
