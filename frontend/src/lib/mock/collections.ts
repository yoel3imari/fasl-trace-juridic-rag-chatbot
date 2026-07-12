import { delay, USER_ID, generateId, now, paginate } from './_shared';

export interface CollectionResponse {
  id: string;
  user_id: string;
  name: string;
  created_at: string;
}

export interface CollectionListResponse {
  collections: CollectionResponse[];
  total: number;
}

export interface CollectionDocumentResponse {
  id: string;
  filename: string;
  language: string;
  status: string;
}

export interface CollectionDocumentsResponse {
  documents: CollectionDocumentResponse[];
  total: number;
}

const collections: CollectionResponse[] = [
  {
    id: 'a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d',
    user_id: USER_ID,
    name: 'Delaware Corp Law 2024',
    created_at: '2024-01-15T10:30:00Z',
  },
  {
    id: 'b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e',
    user_id: USER_ID,
    name: 'M&A Due Diligence',
    created_at: '2024-02-20T14:00:00Z',
  },
  {
    id: 'c3d4e5f6-a7b8-4c9d-0e1f-2a3b4c5d6e7f',
    user_id: USER_ID,
    name: 'Employment Agreements Q1',
    created_at: '2024-03-05T09:15:00Z',
  },
  {
    id: 'd4e5f6a7-b8c9-4d0e-1f2a-3b4c5d6e7f8a',
    user_id: USER_ID,
    name: 'Commercial Lease Precedents',
    created_at: '2024-03-18T11:45:00Z',
  },
  {
    id: 'e5f6a7b8-c9d0-4e1f-2a3b-4c5d6e7f8a9b',
    user_id: USER_ID,
    name: 'IP Licensing Framework',
    created_at: '2024-04-02T08:30:00Z',
  },
  {
    id: 'f6a7b8c9-d0e1-4f2a-3b4c-5d6e7f8a9b0c',
    user_id: USER_ID,
    name: 'Data Privacy Compliance',
    created_at: '2024-04-22T16:20:00Z',
  },
  {
    id: 'a7b8c9d0-e1f2-4a3b-4c5d-6e7f8a9b0c1d',
    user_id: USER_ID,
    name: 'SEC Enforcement Actions',
    created_at: '2024-05-10T13:00:00Z',
  },
  {
    id: 'b8c9d0e1-f2a3-4b4c-5d6e-7f8a9b0c1d2e',
    user_id: USER_ID,
    name: 'Venture Capital Term Sheets',
    created_at: '2024-05-28T10:00:00Z',
  },
  {
    id: 'c9d0e1f2-a3b4-4c5d-6e7f-8a9b0c1d2e3f',
    user_id: USER_ID,
    name: 'Real Estate Purchase Agreements',
    created_at: '2024-06-15T15:30:00Z',
  },
  {
    id: 'd0e1f2a3-b4c5-4d6e-7f8a-9b0c1d2e3f4a',
    user_id: USER_ID,
    name: 'International Arbitration',
    created_at: '2024-07-01T09:00:00Z',
  },
  {
    id: 'e1f2a3b4-c5d6-4e7f-8a9b-0c1d2e3f4a5b',
    user_id: USER_ID,
    name: 'Healthcare Regulatory',
    created_at: '2024-07-20T14:45:00Z',
  },
  {
    id: 'f2a3b4c5-d6e7-4f8a-9b0c-1d2e3f4a5b6c',
    user_id: USER_ID,
    name: 'Financial Services Compliance',
    created_at: '2024-08-12T11:15:00Z',
  },
  {
    id: 'a3b4c5d6-e7f8-4a9b-0c1d-2e3f4a5b6c7d',
    user_id: USER_ID,
    name: 'Shareholder Agreements',
    created_at: '2024-09-05T08:00:00Z',
  },
  {
    id: 'b4c5d6e7-f8a9-4b0c-1d2e-3f4a5b6c7d8e',
    user_id: USER_ID,
    name: 'Non-Profit Bylaws',
    created_at: '2024-10-01T16:30:00Z',
  },
  {
    id: 'c5d6e7f8-a9b0-4c1d-2e3f-4a5b6c7d8e9f',
    user_id: USER_ID,
    name: 'E-Discovery Guidelines',
    created_at: '2024-10-20T12:00:00Z',
  },
];

const collectionDocuments: Map<string, string[]> = new Map();

collectionDocuments.set('a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d', [
  'd1111111-aaaa-4b1c-8d2e-3f4a5b6c7d8e',
  'd2222222-bbbb-4c2d-8e3f-4a5b6c7d8e9f',
]);
collectionDocuments.set('b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e', [
  'd3333333-cccc-4d3e-8f4a-5b6c7d8e9f0a',
  'd4444444-dddd-4e4f-8a5b-6c7d8e9f0a1b',
]);
collectionDocuments.set('c3d4e5f6-a7b8-4c9d-0e1f-2a3b4c5d6e7f', [
  'd5555555-eeee-4f5a-8b6c-7d8e9f0a1b2c',
]);

export async function listCollections({
  skip,
  limit,
  search,
}: {
  skip?: number;
  limit?: number;
  search?: string;
}): Promise<CollectionListResponse> {
  await delay();

  let filtered = collections;
  if (search) {
    const q = search.toLowerCase();
    filtered = collections.filter((c) => c.name.toLowerCase().includes(q));
  }

  const total = filtered.length;
  const items = paginate(filtered, skip, limit);

  return { collections: items, total };
}

export async function createCollection({
  name,
}: {
  name: string;
}): Promise<CollectionResponse> {
  await delay();

  const collection: CollectionResponse = {
    id: generateId(),
    user_id: USER_ID,
    name,
    created_at: now(),
  };

  collections.push(collection);
  return collection;
}

export async function deleteCollection(id: string): Promise<void> {
  await delay();

  const idx = collections.findIndex((c) => c.id === id);
  if (idx === -1) {
    throw new Error(`Collection not found: ${id}`);
  }
  collections.splice(idx, 1);
  collectionDocuments.delete(id);
}

export async function getCollection(id: string): Promise<CollectionResponse> {
  await delay();

  const collection = collections.find((c) => c.id === id);
  if (!collection) {
    throw new Error(`Collection not found: ${id}`);
  }
  return collection;
}

export async function addDocumentsToCollection(
  id: string,
  docIds: string[],
): Promise<CollectionDocumentsResponse> {
  await delay();

  if (!collections.find((c) => c.id === id)) {
    throw new Error(`Collection not found: ${id}`);
  }

  const existing = collectionDocuments.get(id) ?? [];
  const merged = [...new Set([...existing, ...docIds])];
  collectionDocuments.set(id, merged);

  const { getDocumentsByIds } = await import('./documents');
  const docs = getDocumentsByIds(merged);

  return { documents: docs, total: docs.length };
}

export async function removeDocumentFromCollection(
  id: string,
  docId: string,
): Promise<void> {
  await delay();

  if (!collections.find((c) => c.id === id)) {
    throw new Error(`Collection not found: ${id}`);
  }

  const existing = collectionDocuments.get(id);
  if (!existing) return;

  collectionDocuments.set(
    id,
    existing.filter((d) => d !== docId),
  );
}

export async function listDocumentsInCollection(
  id: string,
): Promise<CollectionDocumentsResponse> {
  await delay();

  const docIds = collectionDocuments.get(id) ?? [];

  const { getDocumentsByIds } = await import('./documents');
  const docs = getDocumentsByIds(docIds);

  return { documents: docs, total: docs.length };
}
