# Plan: Adopt `nextjs-fastapi-template` Practices (No Vercel)

**Target**: Bring `precise-rag` in line with production patterns from [vintasoftware/nextjs-fastapi-template](https://github.com/vintasoftware/nextjs-fastapi-template), excluding Vercel deployment.

**Date**: 2026-05-02

---

## Gap Summary

| Practice | Template | Our Project | Action |
|---|---|---|---|
| OpenAPI Client Gen | `@hey-api/openapi-ts` | None | **Add pipeline** |
| Watcher Chain | `watchdog` → `chokidar` | None | **Add both** |
| Server Actions | `"use server"` typed calls | None (frontend is stub) | **Add pattern** |
| Zod Validation | `definitions.ts` | None | **Add** |
| Makefile | 20+ dev commands | None | **Add** |
| Package Manager | pnpm | npm | **Migrate** |
| Pre-commit Hooks | Ruff + ESLint | None | **Add** |
| Start Scripts | `start.sh` for each | Docker CMD only | **Add** |
| Test DB | Separate container | None | **Add** |
| MailHog | Dev email server | None | **Add** |
| Coverage Config | Coveralls CI | None | **Add locally** |
| Auth | `fastapi-users` (JWT) | Supabase Auth | **Keep Supabase** |

> **Supabase Auth is preserved** — it's more production-ready than `fastapi-users` (RLS, managed JWT, social auth). We only need to ensure the OpenAPI schema reflects the auth model.

---

## Phase 1: OpenAPI Client Generation Foundation

**Goal**: Backend auto-generates `openapi.json` → frontend auto-generates typed TypeScript client.

### 1.1 — Backend: OpenAPI schema generator

**Files to create/modify:**

- `backend/commands/__init__.py` — Package init
- `backend/commands/generate_openapi_schema.py` — Schema generator script
  - Import FastAPI app, call `app.openapi()`
  - Strip tag prefixes from operation IDs for clean function names
  - Write to shared location (`OPENAPI_OUTPUT_FILE` env var)
  - Accept output file path as CLI argument or env var fallback

- `backend/main.py` — Add `openapi_url` and `generate_unique_id_function`:
  ```python
  app = FastAPI(
      title="precise-rag",
      openapi_url=settings.OPENAPI_URL,
      generate_unique_id_function=simple_generate_unique_route_id,
      ...
  )
  ```

- `backend/app/core/config.py` — Add `OPENAPI_URL` setting
- `backend/app/utils.py` — Add `simple_generate_unique_route_id` helper

**Verification**: `uv run python -m commands.generate_openapi_schema` writes `openapi.json`.

### 1.2 — Shared openapi.json location

- Create `local-shared-data/` directory at project root
- In `docker-compose.yml`: mount as shared volume on both backend and frontend:
  ```yaml
  # backend service
  volumes:
    - ./local-shared-data:/app/shared-data
  environment:
    - OPENAPI_OUTPUT_FILE=./shared-data/openapi.json

  # frontend service
  volumes:
    - ./local-shared-data:/app/shared-data
  environment:
    - OPENAPI_OUTPUT_FILE=./shared-data/openapi.json
  ```

- For local dev: `OPENAPI_OUTPUT_FILE=../frontend/openapi.json`

### 1.3 — Frontend: Install and configure codegen

**Dependencies to add to `frontend/package.json`:**
```json
"devDependencies": {
  "@hey-api/openapi-ts": "^0.83.1",
  "@hey-api/client-fetch": "^0.13.1",
  "chokidar": "^4.0.1"
}
```

**New file: `frontend/openapi-ts.config.ts`:**
```typescript
import { defineConfig } from "@hey-api/openapi-ts";
import { config } from "dotenv";
config({ path: ".env.local" });

const openapiFile = process.env.OPENAPI_OUTPUT_FILE;

export default defineConfig({
  input: openapiFile as string,
  output: {
    format: "prettier",
    lint: "eslint",
    path: "src/app/openapi-client",
  },
  plugins: ["@hey-api/client-fetch"],
});
```

**Scripts to add to `package.json`:**
```json
"generate-client": "openapi-ts"
```

### 1.4 — Client configuration

**New file: `frontend/src/lib/clientConfig.ts`:**
```typescript
import { client } from "@/app/openapi-client/client.gen";

const configureClient = () => {
  const baseURL = process.env.NEXT_PUBLIC_API_URL;
  client.setConfig({ baseURL });
};

configureClient();
```

**New file: `frontend/src/app/clientService.ts`:**
```typescript
export * from "./openapi-client";
import "@/lib/clientConfig";
```

### 1.5 — Generate initial client

Run:
```bash
cd backend && uv run python -m commands.generate_openapi_schema
cd frontend && pnpm run generate-client
```

Commit the generated `src/app/openapi-client/` directory.

---

## Phase 2: Hot-Reload Watcher Pipeline

**Goal**: Changing a Pydantic schema in Python auto-regenerates TypeScript types.

### 2.1 — Backend watcher

**Dependency**: Add `watchdog>=5.0.3,<6` to `backend/pyproject.toml` dev deps.

**New file: `backend/watcher.py`**:
- Use `watchdog.observers.Observer` and `FileSystemEventHandler`
- Watch: `app/main.py`, `app/schemas/*.py`, `app/api/**/*.py`
- On change (debounced 1s): run `mypy`, then `generate_openapi_schema`
- Print colored status to console

### 2.2 — Frontend watcher

**New file: `frontend/watcher.js`**:
- Use `chokidar` to watch the `openapi.json` file
- On change: `exec("pnpm run generate-client")`
- Print status to console

### 2.3 — Start scripts

**New file: `backend/start.sh`:**
```bash
#!/bin/bash
if [ -f /.dockerenv ]; then
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
    python watcher.py
else
    uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
    uv run python watcher.py
fi
wait
```

**New file: `frontend/start.sh`:**
```bash
#!/bin/bash
pnpm run dev &
node watcher.js
wait
```

### 2.4 — Update Dockerfiles

- `backend/Dockerfile`: Change CMD to `["sh", "start.sh"]`
- `frontend/Dockerfile`: Change CMD to `["sh", "start.sh"]`, ensure `chokidar` is available in the dev stage

---

## Phase 3: Server Actions + Zod Validation

**Goal**: Typed, validated API calls from frontend to backend.

### 3.1 — Install Zod

**Dependencies to add:**
```json
"dependencies": {
  "zod": "^3.23.8",
  "@hookform/resolvers": "^3.9.1"
}
```

### 3.2 — Create Zod schemas

**New file: `frontend/src/lib/definitions.ts`**:
- Mirrors existing Pydantic schemas for client-side validation:
  - `documentSchema` — name, file
  - `collectionSchema` — name, description
  - `llmProviderSchema` — provider_type, base_url, api_key
  - `modelAssignmentSchema` — provider_id, model_name, system_function
  - `loginSchema` — email, password (for Supabase auth forms)
  - `registerSchema` — email, password, passwordConfirm

### 3.3 — Create Server Actions

**New directory: `frontend/src/components/actions/`**

| File | Purpose |
|---|---|
| `document-actions.ts` | `uploadDocument()`, `fetchDocuments()`, `processDocument()`, `getIngestionStatus()` |
| `collection-actions.ts` | `createCollection()`, `fetchCollections()`, `addDocToCollection()`, `removeDocFromCollection()` |
| `llm-provider-actions.ts` | `createProvider()`, `fetchProviders()`, `updateProvider()`, `deleteProvider()`, `setApiKey()`, `deleteApiKey()` |
| `model-assignment-actions.ts` | `createAssignment()`, `fetchAssignments()`, `updateAssignment()`, `deleteAssignment()`, `healthCheck()` |

**Pattern for each Server Action:**
```typescript
"use server";

import { cookies } from "next/headers";
import { generatedSdkFunction } from "@/app/clientService";
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { mySchema } from "@/lib/definitions";

export async function myAction(prevState: unknown, formData: FormData) {
  // 1. Zod validation
  const validated = mySchema.safeParse({ ... });
  if (!validated.success) return { errors: validated.error.flatten().fieldErrors };

  // 2. Get Supabase session token
  const cookieStore = await cookies();
  const token = cookieStore.get("sb-access-token")?.value;
  // OR get Supabase session cookie name based on @supabase/ssr config

  // 3. Call typed SDK
  const { data, error } = await generatedSdkFunction({
    headers: { Authorization: `Bearer ${token}` },
    body: validated.data,
  });

  // 4. Handle result
  if (error) return { server_error: error };
  revalidatePath("/dashboard");
  redirect("/dashboard");
}
```

> **Auth token**: Uses Supabase's session cookie. Our backend's `get_current_user` dependency already verifies Supabase JWTs locally via PyJWT.

---

## Phase 4: Developer Experience

### 4.1 — Migrate frontend to pnpm

**Steps:**
1. Delete `frontend/package-lock.json`
2. Delete `frontend/node_modules/`
3. Run `pnpm install` in `frontend/`
4. Add to `frontend/package.json`:
   ```json
   "packageManager": "pnpm@10.7.1+sha512.2d92c86b7928dc8284f53494fb4201f983da65f0fb4f0d40baafa5cf628fa31dae3e5968f12466f17df7e97310e30f343a648baea1b9b350685dafafffdf5808"
   ```
5. Update `frontend/Dockerfile`:
   - Install pnpm globally
   - Use `pnpm install --frozen-lockfile` instead of `npm ci`
   - Use `pnpm run dev` instead of `npm run dev`
6. Update docker-compose volumes: add `pnpm-store` named volume

### 4.2 — Create Makefile

**New file: `Makefile`** at project root with commands:

| Command | Action |
|---|---|
| `start-backend` | `cd backend && ./start.sh` |
| `start-frontend` | `cd frontend && ./start.sh` |
| `test-backend` | `cd backend && uv run pytest` |
| `test-frontend` | `cd frontend && pnpm run test` |
| `coverage-backend` | `cd backend && uv run coverage run -m pytest && uv run coverage report` |
| `docker-build` | `docker compose build` |
| `docker-up` | `docker compose up -d` |
| `docker-down` | `docker compose down` |
| `docker-logs` | `docker compose logs -f` |
| `docker-migrate-db` | `docker compose run --rm backend alembic upgrade head` |
| `docker-db-schema` | `docker compose run --rm backend alembic revision --autogenerate -m "$(name)"` |
| `docker-test-backend` | `docker compose run --rm backend pytest` |
| `docker-test-frontend` | `docker compose run --rm frontend pnpm run test` |
| `docker-shell-backend` | `docker compose run --rm backend sh` |
| `docker-shell-frontend` | `docker compose run --rm frontend sh` |
| `docker-up-mailhog` | `docker compose up mailhog` |
| `docker-up-test-db` | `docker compose up db_test` |
| `generate-client` | Generate schema + regenerate client |
| `lint` | Run pre-commit on all files |
| `clean` | Remove `__pycache__`, `.pytest_cache`, `node_modules`, `.next` |

### 4.3 — Add pre-commit hooks

**New file: `.pre-commit-config.yaml`:**
```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.8.0
    hooks:
      - id: ruff
        args: [--fix]
        files: ^backend/
      - id: ruff-format
        files: ^backend/

  - repo: https://github.com/pre-commit/mirrors-eslint
    rev: v9.18.0
    hooks:
      - id: eslint
        files: ^frontend/
        args: [--fix]
        additional_dependencies:
          - eslint@9.18.0
          - typescript-eslint@8.20.0
```

**New file: `.pre-commit-config.docker.yaml`** — Docker-based alternative for CI.

### 4.4 — Add test DB and MailHog to docker-compose

**Add to `docker-compose.yml`:**

```yaml
db_test:
  image: postgres:16-alpine
  container_name: precise-rag-db-test
  environment:
    POSTGRES_USER: postgres
    POSTGRES_PASSWORD: password
    POSTGRES_DB: test_precise_rag
  ports:
    - "5433:5432"
  networks:
    - precise-rag-net

mailhog:
  image: mailhog/mailhog
  container_name: precise-rag-mailhog
  ports:
    - "1025:1025"  # SMTP
    - "8025:8025"  # Web UI
  networks:
    - precise-rag-net
```

Add `TEST_DATABASE_URL` to backend service env and `.env.example`.

---

## Phase 5: Quality & Coverage

### 5.1 — Backend coverage

**Dependency**: Add `coverage>=7.6` to `backend/pyproject.toml` dev deps.

**New file: `backend/.coveragerc`:**
```ini
[run]
source = app
omit =
    tests/*
    alembic/*
    commands/*

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise NotImplementedError
    if TYPE_CHECKING:
```

### 5.2 — Frontend testing foundation

**Dependencies to add:**
```json
"devDependencies": {
  "jest": "^29.7.0",
  "@testing-library/react": "^16.0.1",
  "@testing-library/jest-dom": "^6.6.3",
  "jest-environment-jsdom": "^29.7.0",
  "ts-jest": "^29.2.5"
}
```

**New file: `frontend/jest.config.ts`** — Jest configuration for Next.js App Router.

**Add smoke test**: At least one test per Server Action file verifying:
- Valid input → returns data
- Invalid input → returns Zod errors
- Missing auth → redirects/errors

### 5.3 — Update README

- Reflect new tooling (pnpm, Makefile, watchers, generated client)
- Update project structure diagram
- Document the OpenAPI client generation workflow
- Add pre-commit setup instructions
- Update quick start commands

---

## What's Preserved (Not Touched)

| Component | Reason |
|---|---|
| **Supabase Auth** | More production-ready than fastapi-users. RLS, managed JWT, social auth. |
| **Milvus stack** (etcd, minio) | Project-specific vector DB infrastructure. |
| **RAG services** (`pdf_engine`, `llm_service`, `crypto_service`) | Core project IP. |
| **RLS policies** | Tenant isolation at DB level — superior to template's per-query filtering. |
| **Existing DB migrations** | All 5 migration files preserved. |
| **Backend test suite** (66 tests) | All existing tests preserved and run as-is. |
| **SSE streaming plan** | Remains the communication pattern for chat (template uses REST only). |

---

## Execution Order

```
Phase 1 (Foundation)     ← Must be first — everything depends on generated client
  │
Phase 2 (Watchers)       ← Depends on Phase 1 working (watchers watch the pipeline)
  │
Phase 4 (DX)             ← Can run in parallel with Phase 3
  │  └── (Makefile, pnpm, pre-commit independent of Server Actions)
  │
Phase 3 (Server Actions) ← Needs generated client from Phase 1
  │
Phase 5 (Quality)        ← Depends on Phase 3 having actions to test
```

**Parallel opportunities**: Phases 3 + 4 can overlap. Phase 5 follows Phase 3.

---

## Success Criteria

- [ ] Running `uv run python -m commands.generate_openapi_schema` produces valid `openapi.json`
- [ ] Running `pnpm run generate-client` produces typed `sdk.gen.ts` and `types.gen.ts`
- [ ] Changing a Pydantic schema → watcher regenerates OpenAPI → watcher regenerates client
- [ ] All Server Actions validated with Zod before API calls
- [ ] `make docker-up` starts all services including test DB and MailHog
- [ ] `make test-backend` and `make test-frontend` both pass
- [ ] `make lint` (pre-commit) passes on all files
- [ ] `.env.example` updated with all new required variables
- [ ] README updated with new tooling instructions
