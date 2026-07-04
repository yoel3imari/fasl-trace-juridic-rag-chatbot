"use server";

import { cookies } from "next/headers";
import { revalidatePath } from "next/cache";
import {
  listLlmProviders,
  createLlmProvider,
  deleteLlmProvider,
  getLlmProvider,
  updateLlmProvider,
  setProviderApiKey,
  deleteProviderApiKey,
  getProviderApiKeyStatus,
} from "@/app/clientService";
import { llmProviderSchema, apiKeySchema } from "@/lib/definitions";

async function getAuthHeaders() {
  const cookieStore = await cookies();
  const token = cookieStore.get("sb-access-token")?.value;
  if (!token) return null;
  return { Authorization: `Bearer ${token}` };
}

export async function fetchProviders(skip: number = 0, limit: number = 50) {
  const headers = await getAuthHeaders();
  if (!headers) return { error: "Not authenticated" };

  const { data, error } = await listLlmProviders({
    headers,
    query: { skip, limit },
  });
  if (error) return { error: String(error) };
  return { data };
}

export async function createProviderAction(prevState: unknown, formData: FormData) {
  const headers = await getAuthHeaders();
  if (!headers) return { error: "Not authenticated" };

  const validated = llmProviderSchema.safeParse({
    provider_type: formData.get("provider_type"),
    base_url: formData.get("base_url") || undefined,
    api_version: formData.get("api_version") || undefined,
  });
  if (!validated.success) {
    return { errors: validated.error.flatten().fieldErrors };
  }

  const { data, error } = await createLlmProvider({
    headers,
    body: validated.data,
  });
  if (error) return { error: String(error) };
  revalidatePath("/dashboard");
  return { data };
}

export async function updateProviderAction(providerId: string, formData: FormData) {
  const headers = await getAuthHeaders();
  if (!headers) return { error: "Not authenticated" };

  const body: Record<string, any> = {};
  const baseUrl = formData.get("base_url");
  const apiVersion = formData.get("api_version");
  const isActive = formData.get("is_active");

  if (baseUrl !== null) body.base_url = baseUrl || null;
  if (apiVersion !== null) body.api_version = apiVersion || null;
  if (isActive !== null) body.is_active = isActive === "true";

  const { data, error } = await updateLlmProvider({
    headers,
    path: { provider_id: providerId },
    body,
  });
  if (error) return { error: String(error) };
  revalidatePath("/dashboard");
  return { data };
}

export async function deleteProviderAction(providerId: string) {
  const headers = await getAuthHeaders();
  if (!headers) return { error: "Not authenticated" };

  const { error } = await deleteLlmProvider({
    headers,
    path: { provider_id: providerId },
  });
  if (error) return { error: String(error) };
  revalidatePath("/dashboard");
}

export async function setApiKeyAction(providerId: string, formData: FormData) {
  const headers = await getAuthHeaders();
  if (!headers) return { error: "Not authenticated" };

  const validated = apiKeySchema.safeParse({
    api_key: formData.get("api_key"),
  });
  if (!validated.success) {
    return { errors: validated.error.flatten().fieldErrors };
  }

  const { data, error } = await setProviderApiKey({
    headers,
    path: { provider_id: providerId },
    body: validated.data,
  });
  if (error) return { error: String(error) };
  revalidatePath("/dashboard");
  return { data };
}

export async function deleteApiKeyAction(providerId: string) {
  const headers = await getAuthHeaders();
  if (!headers) return { error: "Not authenticated" };

  const { data, error } = await deleteProviderApiKey({
    headers,
    path: { provider_id: providerId },
  });
  if (error) return { error: String(error) };
  revalidatePath("/dashboard");
  return { data };
}
