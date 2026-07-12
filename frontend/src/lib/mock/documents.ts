import { delay, USER_ID, generateId, paginate } from './_shared';

export interface DocumentResponse {
  id: string;
  user_id: string;
  filename: string;
  language: string;
  status: string;
  page_count?: number | null;
  detected_languages?: string[] | null;
  created_at: string;
  updated_at?: string | null;
}

export interface DocumentListResponse {
  documents: DocumentResponse[];
  total: number;
}

export interface IngestionStatusResponse {
  id: string;
  filename: string;
  submitted_language: string;
  status: string;
  page_count?: number | null;
  chunk_count?: number;
  failed_blocks?: number;
  error_log?: Record<string, unknown> | null;
  detected_languages?: string[] | null;
  created_at: string;
  updated_at?: string | null;
}

export interface IngestionStatusListResponse {
  documents: IngestionStatusResponse[];
  total: number;
  skip: number;
  limit: number;
}

type DocumentStatus = 'pending' | 'processing' | 'processed' | 'failed';
type Language = 'en' | 'fr' | 'ar';

interface DocumentRecord {
  id: string;
  filename: string;
  language: Language;
  status: DocumentStatus;
  page_count?: number | null;
  chunk_count?: number;
  failed_blocks?: number;
  error_log?: Record<string, unknown> | null;
  detected_languages?: string[] | null;
  created_at: string;
  updated_at: string;
}

const documents: DocumentRecord[] = [
  {
    id: 'd1111111-aaaa-4b1c-8d2e-3f4a5b6c7d8e',
    filename: 'ServiceAgreement_Acme_v2.pdf',
    language: 'en',
    status: 'processed',
    page_count: 24,
    chunk_count: 96,
    detected_languages: ['en'],
    created_at: '2024-01-10T09:00:00Z',
    updated_at: '2024-01-10T09:05:30Z',
  },
  {
    id: 'd2222222-bbbb-4c2d-8e3f-4a5b6c7d8e9f',
    filename: 'NDA_TechStars_2024.pdf',
    language: 'en',
    status: 'processed',
    page_count: 6,
    chunk_count: 18,
    detected_languages: ['en'],
    created_at: '2024-01-12T14:30:00Z',
    updated_at: '2024-01-12T14:32:15Z',
  },
  {
    id: 'd3333333-cccc-4d3e-8f4a-5b6c7d8e9f0a',
    filename: 'ContratDeDistribution_Paris.pdf',
    language: 'fr',
    status: 'processed',
    page_count: 18,
    chunk_count: 72,
    detected_languages: ['fr', 'en'],
    created_at: '2024-01-15T11:00:00Z',
    updated_at: '2024-01-15T11:06:00Z',
  },
  {
    id: 'd4444444-dddd-4e4f-8a5b-6c7d8e9f0a1b',
    filename: 'MergerAgreement_MegaCorp_2023.pdf',
    language: 'en',
    status: 'processed',
    page_count: 142,
    chunk_count: 568,
    detected_languages: ['en'],
    created_at: '2024-01-20T08:15:00Z',
    updated_at: '2024-01-20T08:35:00Z',
  },
  {
    id: 'd5555555-eeee-4f5a-8b6c-7d8e9f0a1b2c',
    filename: 'EmploymentContract_JohnDoe.pdf',
    language: 'en',
    status: 'processed',
    page_count: 12,
    chunk_count: 36,
    detected_languages: ['en'],
    created_at: '2024-02-01T10:00:00Z',
    updated_at: '2024-02-01T10:03:00Z',
  },
  {
    id: 'd6666666-ffff-4a6b-8c7d-8e9f0a1b2c3d',
    filename: 'AccordDeConfidentialite.pdf',
    language: 'fr',
    status: 'processed',
    page_count: 8,
    chunk_count: 24,
    detected_languages: ['fr'],
    created_at: '2024-02-05T16:45:00Z',
    updated_at: '2024-02-05T16:47:30Z',
  },
  {
    id: 'd7777777-abcd-4b7c-8d8e-9f0a1b2c3d4e',
    filename: 'LicenseAgreement_OpenSource_v3.pdf',
    language: 'en',
    status: 'processed',
    page_count: 15,
    chunk_count: 45,
    detected_languages: ['en'],
    created_at: '2024-02-10T13:20:00Z',
    updated_at: '2024-02-10T13:25:00Z',
  },
  {
    id: 'd8888888-bcde-4c8d-8e9f-0a1b2c3d4e5f',
    filename: 'ProcèsVerbal_ConseilAdministration.pdf',
    language: 'fr',
    status: 'failed',
    page_count: 22,
    chunk_count: 0,
    failed_blocks: 3,
    error_log: {
      step: 'ocr_extraction',
      message: 'Unreadable scanned pages at blocks 7, 8, 14',
      timestamp: '2024-02-12T09:10:00Z',
    },
    detected_languages: ['fr'],
    created_at: '2024-02-12T09:00:00Z',
    updated_at: '2024-02-12T09:10:00Z',
  },
  {
    id: 'd9999999-cdef-4d9e-8f0a-1b2c3d4e5f6a',
    filename: 'TermSheet_SeriesA_Fintech.pdf',
    language: 'en',
    status: 'processed',
    page_count: 10,
    chunk_count: 30,
    detected_languages: ['en'],
    created_at: '2024-02-18T11:00:00Z',
    updated_at: '2024-02-18T11:03:00Z',
  },
  {
    id: 'daaaaaaa-defg-4eaf-8a1b-2c3d4e5f6a7b',
    filename: 'EmploymentAgreement_Exec_2024.pdf',
    language: 'en',
    status: 'processing',
    page_count: null,
    chunk_count: 0,
    detected_languages: null,
    created_at: '2024-03-01T08:00:00Z',
    updated_at: '2024-03-01T08:00:00Z',
  },
  {
    id: 'dbbbbbbb-efgh-4fb0-8b2c-3d4e5f6a7b8c',
    filename: ' عقودالشراكة .pdf',
    language: 'ar',
    status: 'pending',
    page_count: null,
    chunk_count: 0,
    detected_languages: null,
    created_at: '2024-03-05T10:30:00Z',
    updated_at: '2024-03-05T10:30:00Z',
  },
  {
    id: 'dccccccc-fghi-4ac1-8c3d-4e5f6a7b8c9d',
    filename: 'LeaseAgreement_Commercial_SoHo.pdf',
    language: 'en',
    status: 'processed',
    page_count: 35,
    chunk_count: 105,
    detected_languages: ['en'],
    created_at: '2024-03-10T09:15:00Z',
    updated_at: '2024-03-10T09:22:00Z',
  },
  {
    id: 'dddddddd-ghij-4bd2-8d4e-5f6a7b8c9d0e',
    filename: 'BailCommercial_Lyon.pdf',
    language: 'fr',
    status: 'processed',
    page_count: 28,
    chunk_count: 84,
    detected_languages: ['fr', 'en'],
    created_at: '2024-03-15T14:00:00Z',
    updated_at: '2024-03-15T14:09:00Z',
  },
  {
    id: 'deeeeeee-hijk-4ce3-8e5f-6a7b8c9d0e1f',
    filename: 'IPAssignment_Startup_v2.pdf',
    language: 'en',
    status: 'processed',
    page_count: 9,
    chunk_count: 27,
    detected_languages: ['en'],
    created_at: '2024-03-22T11:30:00Z',
    updated_at: '2024-03-22T11:33:00Z',
  },
  {
    id: 'dfffffff-ijkl-4df4-8f6a-7b8c9d0e1f2a',
    filename: 'DataProcessingAgreement_GDPR.pdf',
    language: 'en',
    status: 'processed',
    page_count: 20,
    chunk_count: 60,
    detected_languages: ['en'],
    created_at: '2024-04-01T08:45:00Z',
    updated_at: '2024-04-01T08:50:00Z',
  },
  {
    id: 'd0000001-jklm-4e05-8a7b-8c9d0e1f2a3b',
    filename: 'AccordDeTraitementDesDonnées.pdf',
    language: 'fr',
    status: 'pending',
    page_count: null,
    chunk_count: 0,
    detected_languages: null,
    created_at: '2024-04-05T15:00:00Z',
    updated_at: '2024-04-05T15:00:00Z',
  },
  {
    id: 'd0000002-klmn-4f16-8b8c-9d0e1f2a3b4c',
    filename: '  اتفاقية الترخيص .pdf',
    language: 'ar',
    status: 'failed',
    page_count: null,
    chunk_count: 0,
    failed_blocks: 1,
    error_log: {
      step: 'language_detection',
      message: 'Unsupported character encoding in source file',
      timestamp: '2024-04-08T12:00:00Z',
    },
    detected_languages: null,
    created_at: '2024-04-08T11:55:00Z',
    updated_at: '2024-04-08T12:00:00Z',
  },
  {
    id: 'd0000003-lmno-4a27-8c9d-0e1f2a3b4c5d',
    filename: 'SupplyChain_MasterAgreement.pdf',
    language: 'en',
    status: 'processed',
    page_count: 56,
    chunk_count: 224,
    detected_languages: ['en'],
    created_at: '2024-04-15T10:00:00Z',
    updated_at: '2024-04-15T10:15:00Z',
  },
  {
    id: 'd0000004-mnop-4b38-8d0e-1f2a3b4c5d6e',
    filename: 'NonCompete_Clause_Review.pdf',
    language: 'en',
    status: 'processed',
    page_count: 5,
    chunk_count: 15,
    detected_languages: ['en'],
    created_at: '2024-04-20T13:00:00Z',
    updated_at: '2024-04-20T13:01:30Z',
  },
  {
    id: 'd0000005-nopq-4c49-8e1f-2a3b4c5d6e7f',
    filename: 'JointVenture_EnergyCo.pdf',
    language: 'en',
    status: 'processing',
    page_count: null,
    chunk_count: 0,
    detected_languages: null,
    created_at: '2024-05-02T09:30:00Z',
    updated_at: '2024-05-02T09:30:00Z',
  },
  {
    id: 'd0000006-opqr-4d5a-8f2a-3b4c5d6e7f8a',
    filename: 'أحكام_التعويض .pdf',
    language: 'ar',
    status: 'pending',
    page_count: null,
    chunk_count: 0,
    detected_languages: null,
    created_at: '2024-05-10T11:00:00Z',
    updated_at: '2024-05-10T11:00:00Z',
  },
  {
    id: 'd0000007-pqrs-4e6b-8a3b-4c5d6e7f8a9b',
    filename: 'SPAC_Merger_Terms_2024.pdf',
    language: 'en',
    status: 'processed',
    page_count: 88,
    chunk_count: 352,
    detected_languages: ['en'],
    created_at: '2024-05-18T14:20:00Z',
    updated_at: '2024-05-18T14:35:00Z',
  },
  {
    id: 'd0000008-qrst-4f7c-8b4c-5d6e7f8a9b0c',
    filename: 'ContratDePrestationService.pdf',
    language: 'fr',
    status: 'processed',
    page_count: 14,
    chunk_count: 42,
    detected_languages: ['fr'],
    created_at: '2024-06-01T10:15:00Z',
    updated_at: '2024-06-01T10:18:00Z',
  },
  {
    id: 'd0000009-rstu-4a8d-8c5d-6e7f8a9b0c1d',
    filename: 'SEC_Investigation_Notice_2024.pdf',
    language: 'en',
    status: 'processing',
    page_count: null,
    chunk_count: 0,
    detected_languages: null,
    created_at: '2024-06-10T16:00:00Z',
    updated_at: '2024-06-10T16:00:00Z',
  },
  {
    id: 'd0000010-stuv-4b9e-8d6e-7f8a9b0c1d2e',
    filename: 'EmploymentAgreement_CFO.pdf',
    language: 'en',
    status: 'processed',
    page_count: 18,
    chunk_count: 54,
    detected_languages: ['en'],
    created_at: '2024-06-20T08:30:00Z',
    updated_at: '2024-06-20T08:35:00Z',
  },
  {
    id: 'd0000011-tuvw-4caf-8e7f-8a9b0c1d2e3f',
    filename: 'AssetPurchaseAgreement_v5.pdf',
    language: 'en',
    status: 'failed',
    page_count: 45,
    chunk_count: 120,
    failed_blocks: 2,
    error_log: {
      step: 'chunking',
      message: 'Corrupted PDF structure at pages 22-23, extracted 0 text blocks',
      timestamp: '2024-07-01T11:30:00Z',
    },
    detected_languages: ['en'],
    created_at: '2024-07-01T11:00:00Z',
    updated_at: '2024-07-01T11:30:00Z',
  },
  {
    id: 'd0000012-uvwx-4db0-8f8a-9b0c1d2e3f4a',
    filename: ' اتفاقية_الخدمة .pdf',
    language: 'ar',
    status: 'pending',
    page_count: null,
    chunk_count: 0,
    detected_languages: null,
    created_at: '2024-07-08T12:00:00Z',
    updated_at: '2024-07-08T12:00:00Z',
  },
  {
    id: 'd0000013-vwxy-4ec1-8a9b-0c1d2e3f4a5b',
    filename: 'HealthcareCompliance_Report_Q2.pdf',
    language: 'en',
    status: 'processed',
    page_count: 32,
    chunk_count: 96,
    detected_languages: ['en'],
    created_at: '2024-07-15T09:00:00Z',
    updated_at: '2024-07-15T09:10:00Z',
  },
  {
    id: 'd0000014-wxyz-4fd2-8b0c-1d2e3f4a5b6c',
    filename: 'Indemnification_Clause_Analysis.pdf',
    language: 'en',
    status: 'processing',
    page_count: null,
    chunk_count: 0,
    detected_languages: null,
    created_at: '2024-08-01T14:00:00Z',
    updated_at: '2024-08-01T14:00:00Z',
  },
  {
    id: 'd0000015-xyza-4ae3-8c1d-2e3f4a5b6c7d',
    filename: 'FranchiseAgreement_McDowell.pdf',
    language: 'en',
    status: 'pending',
    page_count: null,
    chunk_count: 0,
    detected_languages: null,
    created_at: '2024-08-10T10:30:00Z',
    updated_at: '2024-08-10T10:30:00Z',
  },
  {
    id: 'd0000016-yzab-4bf4-8d2e-3f4a5b6c7d8e',
    filename: 'AccordDeLicence_Logiciel.pdf',
    language: 'fr',
    status: 'processed',
    page_count: 16,
    chunk_count: 48,
    detected_languages: ['fr', 'en'],
    created_at: '2024-08-22T15:45:00Z',
    updated_at: '2024-08-22T15:50:00Z',
  },
  {
    id: 'd0000017-zabc-4c05-8e3f-4a5b6c7d8e9f',
    filename: 'ClassAction_Settlement_2024.pdf',
    language: 'en',
    status: 'failed',
    page_count: 72,
    chunk_count: 200,
    failed_blocks: 5,
    error_log: {
      step: 'table_extraction',
      message: 'Complex nested tables in pages 31-48 could not be parsed',
      timestamp: '2024-09-01T13:00:00Z',
    },
    detected_languages: ['en'],
    created_at: '2024-09-01T12:00:00Z',
    updated_at: '2024-09-01T13:00:00Z',
  },
  {
    id: 'd0000018-abcd-4d16-8f4a-5b6c7d8e9f0a',
    filename: 'VotingTrustAgreement_Proxy.pdf',
    language: 'en',
    status: 'pending',
    page_count: null,
    chunk_count: 0,
    detected_languages: null,
    created_at: '2024-09-15T09:00:00Z',
    updated_at: '2024-09-15T09:00:00Z',
  },
  {
    id: 'd0000019-bcde-4e27-8a5b-6c7d8e9f0a1b',
    filename: 'Bylaws_NonProfit_Amended.pdf',
    language: 'en',
    status: 'processed',
    page_count: 11,
    chunk_count: 33,
    detected_languages: ['en'],
    created_at: '2024-10-01T10:00:00Z',
    updated_at: '2024-10-01T10:03:00Z',
  },
  {
    id: 'd0000020-cdef-4f38-8b6c-7d8e9f0a1b2c',
    filename: 'E-Discovery_Request_Plaintiff_v2.pdf',
    language: 'en',
    status: 'failed',
    page_count: 160,
    chunk_count: 400,
    failed_blocks: 12,
    error_log: {
      step: 'ocr_extraction',
      message: 'Scanned PDF with mixed handwriting — 12 unreadable blocks',
      timestamp: '2024-10-15T16:30:00Z',
    },
    detected_languages: ['en'],
    created_at: '2024-10-15T15:00:00Z',
    updated_at: '2024-10-15T16:30:00Z',
  },
];

function toDocumentResponse(doc: DocumentRecord): DocumentResponse {
  return {
    id: doc.id,
    user_id: USER_ID,
    filename: doc.filename,
    language: doc.language,
    status: doc.status,
    page_count: doc.page_count ?? null,
    detected_languages: doc.detected_languages ?? null,
    created_at: doc.created_at,
    updated_at: doc.updated_at ?? null,
  };
}

function toIngestionStatus(doc: DocumentRecord): IngestionStatusResponse {
  return {
    id: doc.id,
    filename: doc.filename,
    submitted_language: doc.language,
    status: doc.status,
    page_count: doc.page_count ?? null,
    chunk_count: doc.chunk_count ?? 0,
    failed_blocks: doc.failed_blocks,
    error_log: doc.error_log ?? null,
    detected_languages: doc.detected_languages ?? null,
    created_at: doc.created_at,
    updated_at: doc.updated_at ?? null,
  };
}

export function getDocumentsByIds(ids: string[]): DocumentResponse[] {
  return documents
    .filter((d) => ids.includes(d.id))
    .map(toDocumentResponse);
}

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
  await delay();

  let filtered = [...documents];

  if (status) {
    filtered = filtered.filter((d) => d.status === status);
  }

  if (language) {
    filtered = filtered.filter((d) => d.language === language);
  }

  if (search) {
    const q = search.toLowerCase();
    filtered = filtered.filter((d) => d.filename.toLowerCase().includes(q));
  }

  const total = filtered.length;
  const items = paginate(filtered, skip, limit);

  return {
    documents: items.map(toDocumentResponse),
    total,
  };
}

export async function uploadDocument(
  _file: File,
  language: string,
): Promise<DocumentResponse> {
  await delay(800);

  const id = generateId();
  const doc: DocumentRecord = {
    id,
    filename: _file.name,
    language: (language as Language) || 'en',
    status: 'pending',
    page_count: null,
    chunk_count: 0,
    detected_languages: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };

  documents.unshift(doc);
  return toDocumentResponse(doc);
}

export async function processDocument(id: string): Promise<DocumentResponse> {
  await delay();

  const doc = documents.find((d) => d.id === id);
  if (!doc) {
    throw new Error(`Document not found: ${id}`);
  }

  if (doc.status === 'pending') {
    doc.status = 'processing';
    doc.updated_at = new Date().toISOString();
  }

  setTimeout(() => {
    if (doc.status === 'processing') {
      doc.status = 'processed';
      doc.page_count = Math.floor(Math.random() * 80) + 5;
      doc.chunk_count = doc.page_count * 4;
      doc.detected_languages = [doc.language];
      doc.updated_at = new Date().toISOString();
    }
  }, 3000);

  return toDocumentResponse(doc);
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
  await delay();

  let filtered = [...documents];

  if (status) {
    filtered = filtered.filter((d) => d.status === status);
  }

  const total = filtered.length;
  const items = paginate(filtered, skip, limit);

  return {
    documents: items.map(toIngestionStatus),
    total,
    skip: skip ?? 0,
    limit: limit ?? 10,
  };
}

export async function getDocument(id: string): Promise<DocumentResponse> {
  await delay();

  const doc = documents.find((d) => d.id === id);
  if (!doc) {
    throw new Error(`Document not found: ${id}`);
  }

  return toDocumentResponse(doc);
}


