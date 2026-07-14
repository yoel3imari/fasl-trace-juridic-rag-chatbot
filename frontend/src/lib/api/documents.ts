import { getAuthToken } from './auth';
import * as sdk from '@/app/openapi-client/sdk.gen';
import type {
  DocumentResponse,
  DocumentListResponse,
  IngestionStatusListResponse,
} from '@/app/openapi-client/types.gen';

export async function listDocuments({
  skip,
  limit,
}: {
  skip?: number;
  limit?: number;
  status?: 'pending' | 'processing' | 'processed' | 'failed' | null;
  language?: 'en' | 'fr' | 'ar' | null;
  search?: string;
}): Promise<DocumentListResponse> {
  const token = await getAuthToken();
  if (!token) return { documents: [], total: 0 };
  const { data, error } = await sdk.listDocuments({
    query: { skip, limit },
    headers: { Authorization: `Bearer ${token}` },
  });
  if (error) throw error;
  return data;
}

export async function uploadDocument(
  file: File,
  language: string,
): Promise<DocumentResponse> {
  const token = await getAuthToken();
  const { data, error } = await sdk.uploadDocument({
    body: { file: file as unknown as string, language },
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  if (error) throw error;
  return data;
}

export async function processDocument(id: string): Promise<DocumentResponse> {
  const token = await getAuthToken();
  const { data, error } = await sdk.processDocumentEndpoint({
    path: { document_id: id },
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  if (error) throw error;
  return data as DocumentResponse;
}

export async function getIngestionStatus({
  skip,
  limit,
  status,
}: {
  skip?: number;
  limit?: number;
  status?: 'pending' | 'processing' | 'processed' | 'failed' | null;
}): Promise<IngestionStatusListResponse> {
  const token = await getAuthToken();
  if (!token) return { documents: [], total: 0, skip: skip ?? 0, limit: limit ?? 10 };
  const { data, error } = await sdk.getIngestionStatus({
    query: { skip, limit, status },
    headers: { Authorization: `Bearer ${token}` },
  });
  if (error) throw error;
  return data;
}

export async function getDocument(id: string): Promise<DocumentResponse> {
  const token = await getAuthToken();
  const { data, error } = await sdk.getDocument({
    path: { document_id: id },
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  if (error) throw error;
  return data;
}
