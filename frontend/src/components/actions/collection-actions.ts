"use server";

import { cookies } from "next/headers";
import { revalidatePath } from "next/cache";
import {
  listCollections,
  createCollection,
  deleteCollection,
  getCollection,
  addDocumentsToCollection,
  removeDocumentFromCollection,
  listDocumentsInCollection,
} from "@/app/clientService";
import { collectionSchema } from "@/lib/definitions";

async function getAuthHeaders() {
  const cookieStore = await cookies();
  const token = cookieStore.get("sb-access-token")?.value;
  if (!token) return null;
  return { Authorization: `Bearer ${token}` };
}

export async function fetchCollections(skip: number = 0, limit: number = 20) {
  const headers = await getAuthHeaders();
  // Collections may not require auth headers — let the backend handle it
  const { data, error } = await listCollections({ query: { skip, limit } });
  if (error) return { error: String(error) };
  return { data };
}

export async function createCollectionAction(prevState: unknown, formData: FormData) {
  const headers = await getAuthHeaders();
  if (!headers) return { error: "Not authenticated" };

  const validated = collectionSchema.safeParse({
    name: formData.get("name"),
  });
  if (!validated.success) {
    return { errors: validated.error.flatten().fieldErrors };
  }

  const { data, error } = await createCollection({
    headers,
    body: validated.data,
  });
  if (error) return { error: String(error) };
  revalidatePath("/dashboard");
  return { data };
}

export async function deleteCollectionAction(collectionId: string) {
  const headers = await getAuthHeaders();
  if (!headers) return { error: "Not authenticated" };

  const { error } = await deleteCollection({
    headers,
    path: { collection_id: collectionId },
  });
  if (error) return { error: String(error) };
  revalidatePath("/dashboard");
}

export async function addDocsToCollectionAction(collectionId: string, documentIds: string[]) {
  const headers = await getAuthHeaders();
  if (!headers) return { error: "Not authenticated" };

  const { data, error } = await addDocumentsToCollection({
    headers,
    path: { collection_id: collectionId },
    body: documentIds,
  });
  if (error) return { error: String(error) };
  revalidatePath("/dashboard");
  return { data };
}

export async function removeDocFromCollectionAction(collectionId: string, documentId: string) {
  const headers = await getAuthHeaders();
  if (!headers) return { error: "Not authenticated" };

  const { error } = await removeDocumentFromCollection({
    headers,
    path: { collection_id: collectionId, document_id: documentId },
  });
  if (error) return { error: String(error) };
  revalidatePath("/dashboard");
}
