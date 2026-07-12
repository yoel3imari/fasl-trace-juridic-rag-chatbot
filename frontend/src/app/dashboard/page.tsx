import type { Metadata } from "next";
import { AppShell } from "@/components/layout/AppShell";
import { CollectionList } from "@/components/features/dashboard/CollectionList";
import { DocumentTable } from "@/components/features/dashboard/DocumentTable";

export const metadata: Metadata = {
  title: "Document Ingestion | Fasl Trace",
};

export default function DashboardPage() {
  return (
    <AppShell>
      <div className="flex flex-col gap-8 p-6 max-w-7xl mx-auto w-full">
        <div>
          <h1 className="text-2xl font-semibold text-foreground tracking-tight">
            Document Ingestion
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Upload PDF documents, manage collections, and monitor processing status.
          </p>
        </div>
        <section aria-label="Collections">
          <CollectionList />
        </section>
        <section aria-label="Documents">
          <DocumentTable />
        </section>
      </div>
    </AppShell>
  );
}
