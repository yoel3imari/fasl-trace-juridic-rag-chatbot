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
- **Python** ≥ 3.12 (if running without Docker)
- **uv** (Python package manager) — `curl -LsSf https://astral.sh/uv/install.sh | sh` (or `pip install uv`)
- **Supabase** project (free tier works) — [supabase.com](https://supabase.com). Copy the URL, Anon Key, Service Role Key, and JWT Secret into your `.env` file from the dashboard.

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
npm install
npm run dev
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

## Project Structure

```
precise-rag/
├── frontend/          # Next.js application
│   └── src/
│       ├── app/       # App Router pages
│       ├── components/
│       │   ├── ui/          # shadcn primitives
│       │   └── features/    # Business logic components
│       ├── lib/       # Supabase client, utilities
│       │   ├── supabase.ts
│       │   └── utils.ts
│       └── store/     # Zustand state management
│           └── useChatStore.ts
├── backend/           # FastAPI application
│   ├── app/
│   │   ├── api/v1/    # API routers
│   │   │   └── router_health.py
│   │   ├── core/      # Config & security
│   │   │   ├── config.py
│   │   │   └── security.py
│   │   ├── models/    # SQLAlchemy models
│   │   │   ├── base.py
│   │   │   ├── collection.py
│   │   │   └── document.py
│   │   ├── schemas/   # Pydantic schemas
│   │   └── services/  # ML/RAG orchestration
│   ├── alembic/       # Database migrations
│   └── tests/         # Pytest suites
└── supabase/          # RLS policies & config
```

## Environment Variables

See [`.env.example`](.env.example) for all required variables.

## License

Private — Portfolio Project
