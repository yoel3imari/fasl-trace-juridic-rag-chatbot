import { getAuthToken } from './auth';
import * as sdk from '@/app/openapi-client/sdk.gen';
import type {
  CollectionResponse,
  CollectionListResponse,
  CollectionDocumentResponse,
  CollectionDocumentsResponse,
} from '@/app/openapi-client/types.gen';

export async function listCollections({
  skip,
  limit,
  search,
}: {
  skip?: number;
  limit?: number;
  search?: string;
}): Promise<CollectionListResponse> {
  const token = await getAuthToken();
  if (!token) throw new Error('Not authenticated');
  const { data, error } = await sdk.listCollections({
    query: { skip, limit },
    headers: { Authorization: `Bearer ${token}` },
  });
  if (error) throw error;
  return data;
}

export async function createCollection({
  name,
}: {
  name: string;
}): Promise<CollectionResponse> {
  const token = await getAuthToken();
  if (!token) throw new Error('Not authenticated');
  const { data, error } = await sdk.createCollection({
    body: { name },
    headers: { Authorization: `Bearer ${token}` },
  });
  if (error) throw error;
  return data;
}

export async function deleteCollection(id: string): Promise<void> {
  const token = await getAuthToken();
  if (!token) throw new Error('Not authenticated');
  const { data, error } = await sdk.deleteCollection({
    path: { collection_id: id },
    headers: { Authorization: `Bearer ${token}` },
  });
  if (error) throw error;
  return data;
}

export async function getCollection(id: string): Promise<CollectionResponse> {
  const token = await getAuthToken();
  if (!token) throw new Error('Not authenticated');
  const { data, error } = await sdk.getCollection({
    path: { collection_id: id },
    headers: { Authorization: `Bearer ${token}` },
  });
  if (error) throw error;
  return data;
}

export async function addDocumentsToCollection(
  id: string,
  docIds: string[],
): Promise<CollectionDocumentsResponse> {
  const token = await getAuthToken();
  if (!token) throw new Error('Not authenticated');
  const { data, error } = await sdk.addDocumentsToCollection({
    path: { collection_id: id },
    body: docIds,
    headers: { Authorization: `Bearer ${token}` },
  });
  if (error) throw error;
  return data;
}

export async function removeDocumentFromCollection(
  id: string,
  docId: string,
): Promise<void> {
  const token = await getAuthToken();
  if (!token) throw new Error('Not authenticated');
  const { data, error } = await sdk.removeDocumentFromCollection({
    path: { collection_id: id, document_id: docId },
    headers: { Authorization: `Bearer ${token}` },
  });
  if (error) throw error;
  return data;
}

export async function listDocumentsInCollection(
  id: string,
): Promise<CollectionDocumentsResponse> {
  const token = await getAuthToken();
  if (!token) throw new Error('Not authenticated');
  const { data, error } = await sdk.listDocumentsInCollection({
    path: { collection_id: id },
    headers: { Authorization: `Bearer ${token}` },
  });
  if (error) throw error;
  return data;
}
