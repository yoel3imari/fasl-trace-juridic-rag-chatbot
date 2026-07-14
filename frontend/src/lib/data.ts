/**
 * Data layer switching point.
 *
 * Currently connects to the backend API via the generated OpenAPI SDK.
 * To switch back to mock data for offline/testing:
 *
 *   import * as mockModule from "./mock";
 *   export const api = mockModule;
 *   // ... and update type imports below to point to "./mock/..."
 *
 * The mock and API modules share identical function signatures, so
 * swapping takes effect instantly — zero component changes needed.
 */

import "./clientConfig";
import * as apiModule from "./api";

export const api = apiModule;

export type { CollectionResponse, CollectionListResponse, CollectionDocumentResponse, CollectionDocumentsResponse } from "@/app/openapi-client/types.gen";
export type { DocumentResponse, DocumentListResponse, IngestionStatusResponse, IngestionStatusListResponse } from "@/app/openapi-client/types.gen";
export type { LlmProviderResponse, LlmProviderListResponse, ApiKeyResponse } from "@/app/openapi-client/types.gen";
export type { ModelAssignmentResponse, ModelAssignmentListResponse } from "@/app/openapi-client/types.gen";

/** @deprecated Mock-only — has no effect when using the real API adapter. */
export { setMockLatency } from "./mock";
