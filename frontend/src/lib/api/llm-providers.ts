import { getAuthToken } from './auth';
import * as sdk from '@/app/openapi-client/sdk.gen';
import type {
  LlmProviderResponse,
  LlmProviderListResponse,
  ApiKeyResponse,
} from '@/app/openapi-client/types.gen';

export async function listLlmProviders({
  skip,
  limit,
}: {
  skip?: number;
  limit?: number;
}): Promise<LlmProviderListResponse> {
  const token = await getAuthToken();
  if (!token) return { items: [], total: 0, skip: skip ?? 0, limit: limit ?? 10 };
  const { data, error } = await sdk.listLlmProviders({
    query: { skip, limit },
    headers: { Authorization: `Bearer ${token}` },
  });
  if (error) throw error;
  return data;
}

export async function createLlmProvider({
  provider_type,
  base_url,
  api_version,
}: {
  provider_type: 'openai' | 'anthropic' | 'ollama';
  base_url?: string | null;
  api_version?: string | null;
}): Promise<LlmProviderResponse> {
  const token = await getAuthToken();
  const { data, error } = await sdk.createLlmProvider({
    body: { provider_type, base_url, api_version },
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  if (error) throw error;
  return data;
}

export async function deleteLlmProvider(id: string): Promise<void> {
  const token = await getAuthToken();
  const { data, error } = await sdk.deleteLlmProvider({
    path: { provider_id: id },
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  if (error) throw error;
  return data;
}

export async function getLlmProvider(id: string): Promise<LlmProviderResponse> {
  const token = await getAuthToken();
  const { data, error } = await sdk.getLlmProvider({
    path: { provider_id: id },
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  if (error) throw error;
  return data;
}

export async function updateLlmProvider(
  id: string,
  data: {
    base_url?: string | unknown | null;
    api_version?: string | null;
    is_active?: boolean | null;
  },
): Promise<LlmProviderResponse> {
  const token = await getAuthToken();
  const { data: responseData, error } = await sdk.updateLlmProvider({
    path: { provider_id: id },
    body: data,
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  if (error) throw error;
  return responseData;
}

export async function setProviderApiKey(
  id: string,
  { api_key }: { api_key: string },
): Promise<ApiKeyResponse> {
  const token = await getAuthToken();
  const { data, error } = await sdk.setProviderApiKey({
    path: { provider_id: id },
    body: { api_key },
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  if (error) throw error;
  return data;
}

export async function getProviderApiKeyStatus(
  id: string,
): Promise<ApiKeyResponse> {
  const token = await getAuthToken();
  const { data, error } = await sdk.getProviderApiKeyStatus({
    path: { provider_id: id },
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  if (error) throw error;
  return data;
}

export async function deleteProviderApiKey(
  id: string,
): Promise<ApiKeyResponse> {
  const token = await getAuthToken();
  const { data, error } = await sdk.deleteProviderApiKey({
    path: { provider_id: id },
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  if (error) throw error;
  return data;
}
