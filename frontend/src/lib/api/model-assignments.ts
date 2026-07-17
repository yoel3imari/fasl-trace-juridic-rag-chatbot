import { getAuthToken } from './auth';
import * as sdk from '@/app/openapi-client/sdk.gen';
import type {
  ModelAssignmentResponse,
  ModelAssignmentListResponse,
  PingModelAssignmentResponse,
} from '@/app/openapi-client/types.gen';

export async function listModelAssignments({
  skip,
  limit,
  system_function,
}: {
  skip?: number;
  limit?: number;
  system_function?: string | null;
}): Promise<ModelAssignmentListResponse> {
  const token = await getAuthToken();
  if (!token) return { items: [], total: 0, skip: skip ?? 0, limit: limit ?? 10 };
  const { data, error } = await sdk.listModelAssignments({
    query: { skip, limit, system_function },
    headers: { Authorization: `Bearer ${token}` },
  });
  if (error) throw error;
  return data;
}

export async function createModelAssignment({
  provider_id,
  model_name,
  system_function,
}: {
  provider_id: string;
  model_name: string;
  system_function: 'retrieval' | 'generation' | 'evaluation';
}): Promise<ModelAssignmentResponse> {
  const token = await getAuthToken();
  const { data, error } = await sdk.createModelAssignment({
    body: { provider_id, model_name, system_function },
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  if (error) throw error;
  return data;
}

export async function deleteModelAssignment(id: string): Promise<void> {
  const token = await getAuthToken();
  const { data, error } = await sdk.deleteModelAssignment({
    path: { assignment_id: id },
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  if (error) throw error;
  return data;
}

export async function getModelAssignment(
  id: string,
): Promise<ModelAssignmentResponse> {
  const token = await getAuthToken();
  const { data, error } = await sdk.getModelAssignment({
    path: { assignment_id: id },
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  if (error) throw error;
  return data;
}

export async function updateModelAssignment(
  id: string,
  data: {
    model_name?: string | null;
    is_active?: boolean | null;
    provider_id?: string | null;
  },
): Promise<ModelAssignmentResponse> {
  const token = await getAuthToken();
  const { data: responseData, error } = await sdk.updateModelAssignment({
    path: { assignment_id: id },
    body: data,
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  if (error) throw error;
  return responseData;
}

export async function pingModelAssignment(
  id: string,
): Promise<PingModelAssignmentResponse> {
  const token = await getAuthToken();
  const { data, error } = await sdk.pingModelAssignment({
    path: { assignment_id: id },
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  if (error) throw error;
  return data;
}
