import { delay, USER_ID, generateId, now, paginate } from './_shared';

export interface ModelAssignmentResponse {
  id: string;
  user_id: string;
  provider_id: string;
  model_name: string;
  system_function: 'retrieval' | 'generation' | 'evaluation';
  is_active: boolean;
  health_status?: string | null;
  health_message?: string | null;
  created_at: string;
  updated_at?: string | null;
}

export interface ModelAssignmentListResponse {
  items: ModelAssignmentResponse[];
  total: number;
  skip: number;
  limit: number;
}

interface ModelAssignmentRecord {
  id: string;
  user_id: string;
  provider_id: string;
  model_name: string;
  system_function: 'retrieval' | 'generation' | 'evaluation';
  is_active: boolean;
  health_status: string | null;
  health_message: string | null;
  created_at: string;
  updated_at: string;
}

const assignments: ModelAssignmentRecord[] = [
  {
    id: 'ma000001-aaaa-4b1c-8d2e-3f4a5b6c7d8e',
    user_id: USER_ID,
    provider_id: 'p1000001-aaaa-4b1c-8d2e-3f4a5b6c7d8e',
    model_name: 'gpt-4o',
    system_function: 'generation',
    is_active: true,
    health_status: 'verified',
    health_message: 'Responded to test prompt in 1.2s',
    created_at: '2024-01-20T10:00:00Z',
    updated_at: '2024-06-10T08:00:00Z',
  },
  {
    id: 'ma000002-bbbb-4c2d-8e3f-4a5b6c7d8e9f',
    user_id: USER_ID,
    provider_id: 'p1000001-aaaa-4b1c-8d2e-3f4a5b6c7d8e',
    model_name: 'text-embedding-3-large',
    system_function: 'retrieval',
    is_active: true,
    health_status: 'verified',
    health_message: 'Embedding dimension 3072 verified',
    created_at: '2024-02-01T14:00:00Z',
    updated_at: '2024-05-20T09:30:00Z',
  },
  {
    id: 'ma000003-cccc-4d3e-8f4a-5b6c7d8e9f0a',
    user_id: USER_ID,
    provider_id: 'p2000002-bbbb-4c2d-8e3f-4a5b6c7d8e9f',
    model_name: 'claude-3-5-sonnet-20240620',
    system_function: 'evaluation',
    is_active: true,
    health_status: 'verified',
    health_message: 'Responded to eval prompt in 2.1s',
    created_at: '2024-03-05T11:00:00Z',
    updated_at: '2024-06-01T12:00:00Z',
  },
];

function toResponse(a: ModelAssignmentRecord): ModelAssignmentResponse {
  return {
    id: a.id,
    user_id: a.user_id,
    provider_id: a.provider_id,
    model_name: a.model_name,
    system_function: a.system_function,
    is_active: a.is_active,
    health_status: a.health_status ?? null,
    health_message: a.health_message ?? null,
    created_at: a.created_at,
    updated_at: a.updated_at ?? null,
  };
}

export async function listModelAssignments({
  skip,
  limit,
  system_function,
}: {
  skip?: number;
  limit?: number;
  system_function?: string | null;
}): Promise<ModelAssignmentListResponse> {
  await delay();

  let filtered = [...assignments];

  if (system_function) {
    filtered = filtered.filter(
      (a) => a.system_function === system_function,
    );
  }

  const total = filtered.length;
  const items = paginate(filtered, skip, limit);

  return {
    items: items.map(toResponse),
    total,
    skip: skip ?? 0,
    limit: limit ?? 10,
  };
}

export async function createModelAssignment(data: {
  provider_id: string;
  model_name: string;
  system_function: 'retrieval' | 'generation' | 'evaluation';
}): Promise<ModelAssignmentResponse> {
  await delay();

  const record: ModelAssignmentRecord = {
    id: generateId(),
    user_id: USER_ID,
    provider_id: data.provider_id,
    model_name: data.model_name,
    system_function: data.system_function,
    is_active: true,
    health_status: 'unreachable',
    health_message: 'New assignment — health check pending',
    created_at: now(),
    updated_at: now(),
  };

  assignments.push(record);
  return toResponse(record);
}

export async function getModelAssignment(
  id: string,
): Promise<ModelAssignmentResponse> {
  await delay();

  const a = assignments.find((a) => a.id === id);
  if (!a) {
    throw new Error(`Model assignment not found: ${id}`);
  }
  return toResponse(a);
}

export async function updateModelAssignment(
  id: string,
  data: {
    model_name?: string | null;
    is_active?: boolean | null;
  },
): Promise<ModelAssignmentResponse> {
  await delay();

  const a = assignments.find((a) => a.id === id);
  if (!a) {
    throw new Error(`Model assignment not found: ${id}`);
  }

  if (data.model_name !== undefined && data.model_name !== null) a.model_name = data.model_name;
  if (data.is_active !== undefined && data.is_active !== null) a.is_active = data.is_active;
  a.updated_at = now();

  return toResponse(a);
}

export async function deleteModelAssignment(id: string): Promise<void> {
  await delay();

  const idx = assignments.findIndex((a) => a.id === id);
  if (idx === -1) {
    throw new Error(`Model assignment not found: ${id}`);
  }
  assignments.splice(idx, 1);
}
