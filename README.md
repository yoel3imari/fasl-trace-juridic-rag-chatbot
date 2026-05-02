# Fasl Trace

**High-Fidelity Legal RAG Engine** — An auditable split-pane workspace for Commercial Contracts and Delaware Case Law. Every LLM claim is traced back to its exact bounding box in the source PDF.

## Architecture

| Layer | Stack |
|-------|-------|
| Frontend | Next.js 16, TypeScript, Tailwind CSS, shadcn/ui, Zustand |
| Backend | FastAPI, Python 3.12+, SQLAlchemy 2.0, Alembic |
| Vector DB | Milvus |
| Relational DB | PostgreSQL (Supabase) |
| Auth | Supabase Auth + Postgres RLS |
| Communication | Server-Sent Events (SSE) |

## Prerequisites

- **Docker** & **Docker Compose** (recommended for dev)
- **Node.js** ≥ 20.9 (if running without Docker)
- **pnpm** — `npm install -g pnpm` (if running frontend without Docker)
- **Python** ≥ 3.12 (if running without Docker)
- **uv** (Python package manager) — `curl -LsSf https://astral.sh/uv/install.sh | sh` (or `pip install uv`)
- **Supabase** project (free tier works) — [supabase.com](https://supabase.com). Copy the URL, Anon Key, Service Role Key, and JWT Secret into your `.env` file from the dashboard.
- **pre-commit** — `pip install pre-commit && pre-commit install` (for commit hooks)

## Quick Start (Docker)

```bash
cp .env.example .env
# Edit .env with your Supabase credentials (optional for initial setup)

docker compose up -d
# Run database migrations
docker compose exec backend alembic upgrade head

# Frontend → http://localhost:3000
# Backend  → http://localhost:8000/api/v1/health (returns '{"status": "ok"}')
# Postgres → localhost:5432 (see .env for credentials)
```

## Quick Start (Manual)

### 1. Clone & configure environment

```bash
cp .env.example .env
# Edit .env with your Supabase credentials and database URL
```

### 2. Start the frontend

```bash
cd frontend
pnpm install
pnpm run dev
# → http://localhost:3000
```

### 3. Start the backend

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn main:app --reload --port 8000
# → http://localhost:8000/api/v1/health (returns '{"status": "ok"}')
```

## Makefile

Common development commands are available via the project-level `Makefile`:

| Command | Description |
|---------|-------------|
| `make start-backend` | Start backend with hot reload and watcher |
| `make start-frontend` | Start frontend dev server |
| `make test-backend` | Run backend tests (pytest) |
| `make test-frontend` | Run frontend tests (Jest) |
| `make coverage-backend` | Run backend tests with coverage report |
| `make generate-client` | Regenerate OpenAPI schema and TypeScript client |
| `make lint` | Run pre-commit hooks on all files |
| `make clean` | Remove build artifacts and caches |
| `make docker-up` | Start all Docker services |
| `make docker-down` | Stop all Docker services |
| `make docker-migrate-db` | Run database migrations |
| `make docker-test-backend` | Run backend tests in Docker |
| `make docker-test-frontend` | Run frontend tests in Docker |

## OpenAPI Client Generation

The frontend consumes a generated TypeScript client from the backend's OpenAPI schema.

```bash
# Regenerate both schema and client:
make generate-client

# Or step by step:
cd backend && uv run python -m commands.generate_openapi_schema
cd frontend && pnpm run generate-client
```

The generated client lives in `frontend/openapi-client/` and is committed to the repository. The pre-commit hook automatically regenerates it when the OpenAPI schema changes.

## Pre-commit Hooks

This project uses [pre-commit](https://pre-commit.com/) to enforce code quality:

```bash
# Install hooks (one-time)
pre-commit install

# Run on all files
pre-commit run --all-files
```

Hooks include:
- **Ruff** — Python linting and formatting (backend/)
- **ESLint** — TypeScript/React linting (frontend/)
- **OpenAPI schema generation** — auto-regenerates when backend schemas change
- **Frontend client generation** — auto-regenerates when openapi.json changes
- **General checks** — large files, merge conflicts, private keys, etc.

## Watcher Pipeline

The backend includes a file watcher (`backend/watcher.py`) that monitors the `local-shared-data/` directory for changes and automatically triggers OpenAPI schema regeneration. Use `make start-backend` to launch both the FastAPI server and the watcher together.

## Testing

### Backend (pytest)

```bash
cd backend
uv run pytest
# With coverage:
uv run coverage run -m pytest && uv run coverage report
```

### Frontend (Jest + Testing Library)

```bash
cd frontend
pnpm run test
```

Smoke tests verify that server actions and Zod schemas import and behave correctly. Full integration tests require a running backend.

## Project Structure

```
precise-rag/
├── frontend/              # Next.js application
│   ├── jest.config.ts     # Jest configuration
│   ├── jest.setup.ts      # Jest setup (Testing Library matchers)
│   └── src/
│       ├── app/           # App Router pages
│       ├── components/
│       │   ├── actions/        # Server Actions (Zod-validated)
│       │   ├── ui/             # shadcn primitives
│       │   └── features/       # Business logic components
│       ├── lib/           # Supabase client, utilities, Zod schemas
│       │   ├── definitions.ts  # Zod validation schemas
│       │   ├── supabase.ts
│       │   └── utils.ts
│       ├── store/         # Zustand state management
│       │   └── useChatStore.ts
│       └── __tests__/     # Jest smoke tests
│           └── actions.test.ts
├── backend/               # FastAPI application
│   ├── app/
│   │   ├── api/v1/        # API routers
│   │   │   └── router_health.py
│   │   ├── core/          # Config & security
│   │   │   ├── config.py
│   │   │   └── security.py
│   │   ├── models/        # SQLAlchemy models
│   │   │   ├── base.py
│   │   │   ├── collection.py
│   │   │   └── document.py
│   │   ├── schemas/       # Pydantic schemas
│   │   └── services/      # ML/RAG orchestration
│   ├── alembic/           # Database migrations
│   ├── commands/          # CLI commands (OpenAPI generation)
│   ├── watcher.py         # File watcher for auto-regeneration
│   ├── start.sh           # Dev startup script (server + watcher)
│   └── tests/             # Pytest suites
├── supabase/              # RLS policies & config
├── Makefile               # Common dev commands
├── .pre-commit-config.yaml
└── .env.example
```

## Environment Variables

See [`.env.example`](.env.example) for all required variables.

## License

Private — Portfolio Project
