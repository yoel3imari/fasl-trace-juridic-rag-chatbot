# Backend Integration Plan

## Current Architecture

```
Client Components (Dashboard/Settings)
        │
        ▼
  @/lib/data  ←──── switching point, currently →  @/lib/mock/* (fake data)
        │
        ▼
  Server Actions (src/components/actions/*)  ───→  @/app/openapi-client/sdk.gen.ts (real SDK)
        │
        ▼
  FastAPI Backend
```

**Gaps**:
- Client components never reach the real backend — all CRUD goes through mock
- Server Actions use the real SDK but are bypassed by the mock layer
- Chat SSE hook (`useChatStream`) calls the real backend directly via `fetch()` — already wired
- Auth token is fetched from Supabase in `useChatStream` but mock data needs none

---

## Step 1 — Create a real API adapter

**Goal**: A drop-in replacement for `@/lib/mock/*` with the **exact same function signatures**, calling the real backend via the OpenAPI SDK.

**File to create**: `src/lib/api/index.ts`

This file exports the same functions as `src/lib/mock/index.ts`:

- `listCollections`, `createCollection`, `deleteCollection`, `getCollection`
- `listDocuments`, `uploadDocument`, `processDocument`, `getDocument`
- `listLlmProviders`, `createLlmProvider`, `deleteLlmProvider`, `getLlmProvider`, `updateLlmProvider`
- `setProviderApiKey`, `deleteProviderApiKey`, `getProviderApiKeyStatus`
- `listModelAssignments`, `createModelAssignment`, `deleteModelAssignment`, `getModelAssignment`, `updateModelAssignment`
- `addDocumentsToCollection`, `removeDocumentFromCollection`, `listDocumentsInCollection`

**Pattern for each function**:

```typescript
import * as sdk from "@/app/openapi-client/sdk.gen";
// Pass auth token from Supabase session
// Call sdk.listCollections({ headers: { Authorization: `Bearer ${token}` }, query: {...} })
// Transform response to match mock's return type if needed
// Handle errors consistently
```

**Auth approach**: Each function accepts an optional `accessToken` parameter. The adapter gets the token from the Supabase client when not provided. This keeps the API clean for both server-side and client-side use.

**File to create**: `src/lib/api/auth.ts` — helper that wraps Supabase `createClient()` to get the session token, with a clear error when not authed.

---

## Step 2 — Swap the switching point

**File to change**: `src/lib/data.ts`

Change one line:

```typescript
// Before:
import * as mock from "./mock";
export const api = mock;

// After:
import * as apiModule from "./api";
export const api = apiModule;
```

This is the one-line swap the comment at the top of `data.ts` was designed for. All client components (Dashboard, Settings, CollectionList, DocumentTable, ProviderManager, AssignmentManager) immediately use the real backend — no component changes needed.

---

## Step 3 — Wire Supabase auth into the client data flow

**Current state**:
- Mock layer has `USER_ID = '00000000-0000-0000-0000-000000000001'` — no real auth
- `useChatStream.ts` already fetches Supabase session token and passes it as `Authorization: Bearer`
- The real API adapter (Step 1) needs the token

**What to build**:
1. Create `src/lib/auth.ts` — thin wrapper around `@supabase/ssr`'s `createBrowserClient` that exposes `getAccessToken()`
2. Each real API function calls `getAccessToken()` and includes it in headers
3. If no session exists, the API functions throw a clear "Not authenticated" error (the UI already handles this via the mock's `"Not authenticated"` returns)

**Auth UI**:
- Add a Supabase Auth callback route: `app/auth/callback/route.ts`
- Update the TopBar dropdown "Sign out" to actually call `supabase.auth.signOut()`
- Add a login page at `/login` for when the session is missing

---

## Step 4 — Connect the chat SSE to the real backend

**Current state**:
- `useChatStream.ts` already calls `POST /api/v1/chat/stream` with the real backend URL
- It already passes the Supabase access token
- The SSE event parsing matches the backend's event format exactly (`token`, `citation`, `processing_step`, `error`, `warning`, `done`)
- **It should already work** once the backend is running and the user is authenticated

**What to check/verify**:
1. Backend is running (`docker compose up -d`)
2. Backend has the required Milvus + PostgreSQL services healthy
3. A collection with documents exists and has been processed (so retrieval returns results)
4. An LLM provider + model assignment is configured (so generation works)
5. Run a test query via curl first: `curl -X POST http://localhost:8000/api/v1/chat/stream -H "Content-Type: application/json" -H "Authorization: Bearer <token>" -d '{"query": "test"}'`

---

## Step 5 — Clean up dead code

After the swap:
- `src/lib/mock/*` — keep as a reference / fallback (export a `setMockLatency` no-op from the real adapter)
- Server Actions (`src/components/actions/*`) — they already use the real SDK but are no longer used by the client components (since the client now calls the SDK directly via the adapter). Either:
  - **Remove them** if you want Server Actions gone
  - **Keep them** as an alternative server-side entry point (useful for form actions like upload)
- The `data.ts` switching point comment can be removed since the switch is permanent

---

## Execution Order

```
Step 1 (API adapter) ──→ Step 2 (swap data.ts) ──→ Step 3 (auth wiring)
                                                            │
                                                            ▼
                                              Step 4 (verify chat SSE)
                                                            │
                                                            ▼
                                              Step 5 (cleanup)
```

Steps 1–3 can be done in a single PR. Step 4 is verification. Step 5 is optional.

---

## Files to create

| File | Purpose |
|---|---|
| `src/lib/api/index.ts` | Real API adapter — same interface as `src/lib/mock/index.ts` |
| `src/lib/api/auth.ts` | Supabase token helper for client-side |
| `src/app/auth/callback/route.ts` | Supabase auth callback |
| `src/app/login/page.tsx` | Login page |

## Files to modify

| File | Change |
|---|---|
| `src/lib/data.ts` | Swap import from `./mock` to `./api` |
| `src/components/layout/TopBar.tsx` | Wire "Sign out" to `supabase.auth.signOut()` |

## Files to keep (no changes needed)

- All client components (Dashboard, Settings, etc.) — they only import from `@/lib/data`
- All mock files — stay as reference/fallback
- `useChatStream.ts` — already calls real backend
- `useSSEStream.ts` — generic hook, no changes needed
- `src/lib/clientConfig.ts` — already configures the OpenAPI client base URL
