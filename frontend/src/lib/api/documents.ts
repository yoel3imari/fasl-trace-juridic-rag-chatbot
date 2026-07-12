import { getAuthToken } from './auth';
import * as sdk from '@/app/openapi-client/sdk.gen';
import type {
  DocumentResponse,
  DocumentListResponse,
  IngestionStatusResponse,
  IngestionStatusListResponse,
} from '@/app/openapi-client/types.gen';

export async function listDocuments({
  skip,
  limit,
  status,
  language,
  search,
}: {
  skip?: number;
  limit?: number;
  status?: 'pending' | 'processing' | 'processed' | 'failed' | null;
  language?: 'en' | 'fr' | 'ar' | null;
  search?: string;
}): Promise<DocumentListResponse> {
  const token = await getAuthToken();
  if (!token) throw new Error('Not authenticated');
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
  if (!token) throw new Error('Not authenticated');
  const { data, error } = await sdk.uploadDocument({
    body: { file: file as unknown as string, language },
    headers: { Authorization: `Bearer ${token}` },
  });
  if (error) throw error;
  return data;
}

export async function processDocument(id: string): Promise<DocumentResponse> {
  const token = await getAuthToken();
  if (!token) throw new Error('Not authenticated');
  const { data, error } = await sdk.processDocumentEndpoint({
    path: { document_id: id },
    headers: { Authorization: `Bearer ${token}` },
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
  if (!token) throw new Error('Not authenticated');
  const { data, error } = await sdk.getIngestionStatus({
    query: { skip, limit, status },
    headers: { Authorization: `Bearer ${token}` },
  });
  if (error) throw error;
  return data;
}

export async function getDocument(id: string): Promise<DocumentResponse> {
  const token = await getAuthToken();
  if (!token) throw new Error('Not authenticated');
  const { data, error } = await sdk.getDocument({
    path: { document_id: id },
    headers: { Authorization: `Bearer ${token}` },
  });
  if (error) throw error;
  return data;
}
