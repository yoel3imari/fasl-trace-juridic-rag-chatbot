"use server";

import { revalidatePath } from "next/cache";
import { createClient } from "@/lib/supabase-server";
import {
  listDocuments,
  uploadDocument,
  getIngestionStatus,
  getDocument,
} from "@/app/clientService";
import { documentSchema } from "@/lib/definitions";
import type { ListDocumentsData, GetIngestionStatusData } from "@/app/clientService";

async function getAuthHeaders() {
  const supabase = await createClient();
  const { data: { session } } = await supabase.auth.getSession();
  if (!session?.access_token) return null;
  return { Authorization: `Bearer ${session.access_token}` };
}

export async function fetchDocuments(skip: number = 0, limit: number = 20) {
  const headers = await getAuthHeaders();
  if (!headers) return { error: "Not authenticated" };

  const { data, error } = await listDocuments({
    headers,
    query: { skip, limit } as ListDocumentsData["query"],
  });
  if (error) return { error: String(error) };
  return { data };
}

export async function uploadDocumentAction(prevState: unknown, formData: FormData) {
  const headers = await getAuthHeaders();
  if (!headers) return { error: "Not authenticated" };

  const validated = documentSchema.safeParse({
    filename: formData.get("filename"),
    language: formData.get("language"),
  });
  if (!validated.success) {
    return { errors: validated.error.flatten().fieldErrors };
  }

  const file = formData.get("file") as File;
  if (!file) return { errors: { file: ["File is required"] } };

  const { data, error } = await uploadDocument({
    headers,
    body: { file, language: validated.data.language },
  });
  if (error) return { error: String(error) };
  revalidatePath("/dashboard");
  return { data };
}

export async function processDocumentAction(documentId: string) {
  const headers = await getAuthHeaders();
  if (!headers) return { error: "Not authenticated" };

  const { processDocumentEndpoint } = await import("@/app/clientService");
  const { data, error } = await processDocumentEndpoint({
    headers,
    path: { document_id: documentId },
  });
  if (error) return { error: String(error) };
  revalidatePath("/dashboard");
  return { data };
}

export async function fetchIngestionStatus(
  skip: number = 0,
  limit: number = 20,
  status?: string
) {
  const headers = await getAuthHeaders();
  if (!headers) return { error: "Not authenticated" };

  const query: Record<string, any> = { skip, limit };
  if (status) query.status = status;

  const { data, error } = await getIngestionStatus({
    headers,
    query: query as GetIngestionStatusData["query"],
  });
  if (error) return { error: String(error) };
  return { data };
}
