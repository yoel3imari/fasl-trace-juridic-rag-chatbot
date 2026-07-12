import { delay, USER_ID, generateId, now, paginate } from './_shared';

export interface LlmProviderResponse {
  id: string;
  user_id: string;
  provider_type: 'openai' | 'anthropic' | 'ollama';
  base_url?: string | null;
  api_version?: string | null;
  is_active: boolean;
  has_api_key?: boolean;
  warning?: string | null;
  created_at: string;
  updated_at?: string | null;
}

export interface LlmProviderListResponse {
  items: LlmProviderResponse[];
  total: number;
  skip: number;
  limit: number;
}

export interface ApiKeyResponse {
  has_api_key: boolean;
  masked_key?: string | null;
  updated_at?: string | null;
}

interface LlmProviderRecord {
  id: string;
  user_id: string;
  provider_type: 'openai' | 'anthropic' | 'ollama';
  base_url: string | null;
  api_version: string | null;
  is_active: boolean;
  has_api_key: boolean;
  warning: string | null;
  created_at: string;
  updated_at: string;
  api_key: string | null;
}

const providers: LlmProviderRecord[] = [
  {
    id: 'p1000001-aaaa-4b1c-8d2e-3f4a5b6c7d8e',
    user_id: USER_ID,
    provider_type: 'openai',
    base_url: 'https://api.openai.com',
    api_version: 'v1',
    is_active: true,
    has_api_key: true,
    warning: null,
    created_at: '2024-01-15T10:00:00Z',
    updated_at: '2024-06-01T08:00:00Z',
    api_key: 'sk-proj-xxxxxxxxxxxxx',
  },
  {
    id: 'p2000002-bbbb-4c2d-8e3f-4a5b6c7d8e9f',
    user_id: USER_ID,
    provider_type: 'anthropic',
    base_url: 'https://api.anthropic.com',
    api_version: '2023-06-01',
    is_active: true,
    has_api_key: true,
    warning: 'Key expiring in 14 days',
    created_at: '2024-02-20T14:30:00Z',
    updated_at: '2024-05-15T12:00:00Z',
    api_key: 'sk-ant-xxxxxxxxxxxxx',
  },
  {
    id: 'p3000003-cccc-4d3e-8f4a-5b6c7d8e9f0a',
    user_id: USER_ID,
    provider_type: 'ollama',
    base_url: 'http://localhost:11434',
    api_version: null,
    is_active: false,
    has_api_key: false,
    warning: 'Ollama service unreachable — check if server is running',
    created_at: '2024-03-10T09:00:00Z',
    updated_at: '2024-04-01T11:00:00Z',
    api_key: null,
  },
];

function toResponse(p: LlmProviderRecord): LlmProviderResponse {
  return {
    id: p.id,
    user_id: p.user_id,
    provider_type: p.provider_type,
    base_url: p.base_url ?? null,
    api_version: p.api_version ?? null,
    is_active: p.is_active,
    has_api_key: p.has_api_key,
    warning: p.warning ?? null,
    created_at: p.created_at,
    updated_at: p.updated_at ?? null,
  };
}

function maskKey(key: string): string {
  if (key.length <= 8) return key;
  return key.slice(0, 8) + '••••' + key.slice(-4);
}

export async function listLlmProviders({
  skip,
  limit,
}: {
  skip?: number;
  limit?: number;
}): Promise<LlmProviderListResponse> {
  await delay();

  const total = providers.length;
  const items = paginate(providers, skip, limit);

  return {
    items: items.map(toResponse),
    total,
    skip: skip ?? 0,
    limit: limit ?? 10,
  };
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
  await delay();

  const record: LlmProviderRecord = {
    id: generateId(),
    user_id: USER_ID,
    provider_type,
    base_url: base_url ?? null,
    api_version: api_version ?? null,
    is_active: true,
    has_api_key: false,
    warning: null,
    created_at: now(),
    updated_at: now(),
    api_key: null,
  };

  providers.push(record);
  return toResponse(record);
}

export async function getLlmProvider(
  id: string,
): Promise<LlmProviderResponse> {
  await delay();

  const p = providers.find((p) => p.id === id);
  if (!p) {
    throw new Error(`LLM provider not found: ${id}`);
  }
  return toResponse(p);
}

export async function updateLlmProvider(
  id: string,
  data: {
    base_url?: string | unknown | null;
    api_version?: string | null;
    is_active?: boolean | null;
  },
): Promise<LlmProviderResponse> {
  await delay();

  const p = providers.find((p) => p.id === id);
  if (!p) {
    throw new Error(`LLM provider not found: ${id}`);
  }

  if (data.base_url !== undefined) p.base_url = data.base_url as string | null;
  if (data.api_version !== undefined) p.api_version = data.api_version;
  if (data.is_active !== undefined && data.is_active !== null) p.is_active = data.is_active;
  p.updated_at = now();

  return toResponse(p);
}

export async function deleteLlmProvider(id: string): Promise<void> {
  await delay();

  const idx = providers.findIndex((p) => p.id === id);
  if (idx === -1) {
    throw new Error(`LLM provider not found: ${id}`);
  }
  providers.splice(idx, 1);
}

export async function setProviderApiKey(
  id: string,
  { api_key }: { api_key: string },
): Promise<ApiKeyResponse> {
  await delay();

  const p = providers.find((p) => p.id === id);
  if (!p) {
    throw new Error(`LLM provider not found: ${id}`);
  }

  p.api_key = api_key;
  p.has_api_key = true;
  p.updated_at = now();

  return {
    has_api_key: true,
    masked_key: maskKey(api_key),
    updated_at: now(),
  };
}

export async function getProviderApiKeyStatus(
  id: string,
): Promise<ApiKeyResponse> {
  await delay();

  const p = providers.find((p) => p.id === id);
  if (!p) {
    throw new Error(`LLM provider not found: ${id}`);
  }

  if (!p.api_key) {
    return { has_api_key: false, masked_key: null, updated_at: null };
  }

  return {
    has_api_key: p.has_api_key,
    masked_key: maskKey(p.api_key),
    updated_at: p.updated_at,
  };
}

export async function deleteProviderApiKey(
  id: string,
): Promise<ApiKeyResponse> {
  await delay();

  const p = providers.find((p) => p.id === id);
  if (!p) {
    throw new Error(`LLM provider not found: ${id}`);
  }

  p.api_key = null;
  p.has_api_key = false;
  p.updated_at = now();

  return {
    has_api_key: false,
    masked_key: null,
    updated_at: now(),
  };
}
