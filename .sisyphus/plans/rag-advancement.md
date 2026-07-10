# Fasl Trace — RAG Advancement Plan

## Objective
Advance Fasl Trace from a well-structured skeleton (infrastructure built, RAG loop missing) to a functional legal RAG engine with real LLM responses and PDF-grounded citations across English, French, and Arabic.

## Guiding Principles
- **No LangChain/LlamaIndex** — existing custom auth/SSE/provider infra is clean; a 4-stage pipeline doesn't warrant framework overhead.
- **Local embeddings** — BGE-M3 via sentence-transformers (568M params, 1024d, multilingual, Mac-CPU-friendly).
- **Citations v1** — text-based (page + section). Bounding-box pinning deferred to v2.
- **Partition-based RLS** — Milvus partitions keyed by `user_id`; existing auth middleware provides the user context.

---

## Phase 0 — Dependency Installation & Baseline Verification

**Goal**: Install new dependencies, verify the existing codebase still builds and tests pass.

### Steps
1. Install Python deps: `sentence-transformers`, `pymilvus`, `FlashRank`, `numpy<2.0`
2. Verify `docker-compose.yml` has Milvus 2.4+ services running
3. Run existing test suite — confirm baseline
4. Check `lsp_diagnostics` on all existing backend Python files

### Dependencies
```txt
sentence-transformers>=3.0.0
pymilvus>=2.4.0
flashrank>=0.2.0
numpy<2.0
```

### Verification
- `docker compose ps` — milvus, etcd, minio, postgres all healthy
- `pytest` — all existing tests pass
- `lsp_diagnostics` — zero errors on `backend/app/`

---

## Phase 1 — Embedding Service

**Goal**: Singleton embedding service wrapping BGE-M3, with lazy model loading and batch encoding.

### New File: `backend/app/services/embedding_service.py`

- Singleton pattern (same as `crypto_service.py`)
- Lazy-loads `BAAI/bge-m3` model on first call
- Methods:
  - `encode_dense(texts: list[str]) -> list[list[float]]` — 1024-dim dense vectors
  - `encode_sparse(texts: list[str]) -> list[dict[int, float]]` — sparse lexical vectors (Splade-style)
  - `encode_query(text: str) -> tuple[list[float], dict[int, float]]` — query encoding (dense + sparse)
- Config: model name, device ("cpu" for Mac), batch size from settings
- Uses `model.encode(..., normalize_embeddings=True)` for inner product search

### No changes to existing files

---

## Phase 2 — Milvus Vector Store Service

**Goal**: Service layer to manage the Milvus collection, partitions, and CRUD operations.

### New File: `backend/app/services/vector_store_service.py`

- Collection: `fasl_trace_chunks`
- Schema:
  - `id` (INT64, auto_id)
  - `user_id` (INT64) — partition key, RLS boundary
  - `document_id` (INT64)
  - `chunk_index` (INT32)
  - `dense_vector` (FLOAT_VECTOR, 1024d)
  - `sparse_vector` (SPARSE_FLOAT_VECTOR)
  - `text` (VARCHAR, max 65535)
  - `page_number` (INT32)
  - `section_title` (VARCHAR, max 512)
  - `metadata` (JSON)
- Indexes:
  - Dense: IVF_FLAT or HNSW (1024d requires tuning; start IVF_FLAT with nlist=1024)
  - Sparse: SPARSE_INVERTED_INDEX
- Partition: one per `user_id`, created on first write
- Methods:
  - `ensure_collection()` — create collection + indexes if not exist
  - `ensure_partition(user_id)` — create partition if not exist
  - `insert_chunks(user_id, chunks: list[dict]) -> list[int]`
  - `delete_document_chunks(user_id, document_id)`
  - `hybrid_search(user_id, dense_vec, sparse_vec, query_text, top_k=20, filters=None) -> list[dict]`
    - Dense field: `ANN_SEARCH(dense_vector, ...)`
    - Sparse field: `ANN_SEARCH(sparse_vector, ...)`
    - Merge via RRF (Reciprocal Rank Fusion, k=60)
  - `delete_partition(user_id)` — for user deletion

### Config additions (settings.py)
- `MILVUS_HOST`, `MILVUS_PORT`, `MILVUS_COLLECTION`
- `MILVUS_DENSE_INDEX_TYPE`, `MILVUS_SPARSE_INDEX_TYPE`
- `VECTOR_DIMENSION = 1024`

### New File: `backend/app/core/milvus_client.py`
- Singleton Milvus `connections.connect()` wrapper
- Connection pool via `open()`/`close()` context manager pattern

---

## Phase 3 — Chunking Service

**Goal**: Clause-boundary-aware chunker with semantic fallback for legal documents.

### New File: `backend/app/services/chunking_service.py`

- Input: `list[TextBlock]` from `pdf_engine.py` (already has page numbers, bounding boxes, text)
- Pipeline:
  1. **Merge blocks** back into a page-ordered text stream
  2. **Clause-boundary splitting** — regex patterns for:
     - `Article \d+`, `Section \d+`, `Clause \d+`, `المادة`, `الفصل`, `الفقرة`
     - `CHAPTER \d+`, `TITLE \d+`, `PART \d+`
  3. If clause boundaries are sparse → fall back to **semantic chunking** (sentence splitting + merge until 512-1024 tokens)
  4. 20% overlap via sliding window on the fallback path
- Output: `list[Chunk]` with:
  - `text`, `page_number`, `section_title` (extracted from nearest heading), `chunk_index`, `metadata` (lang, bbox list for v2)

### Dependencies
- `tokenizers` (already available via sentence-transformers) for accurate token counting

### No changes to existing files

---

## Phase 4 — Ingestion → Vector Pipeline

**Goal**: Wire upload → PDF extraction → chunk → embed → upsert into Milvus.

### Changes to: `backend/app/api/v1/router_document.py`

- After PDF extraction completes (existing `process_pdf` pipeline):
  1. Call `chunking_service.chunk(text_blocks)`
  2. Call `embedding_service.encode_dense(chunk_texts)` + `encode_sparse(chunk_texts)`
  3. Call `vector_store_service.insert_chunks(user_id, chunks_with_vectors)`
- Update `Document.status` to `"vectorized"` on success, `"vectorization_failed"` on error
- Error handling: if any step fails, mark document as failed (don't leave in inconsistent state)

### May create: `backend/app/services/pipeline_service.py`
- Orchestrator that chains: chunk → embed → upsert
- Keeps `router_document.py` thin (single call to `pipeline_service.run(document_id, user_id, text_blocks)`)

---

## Phase 5 — Query Router + Retrieval Pipeline

**Goal**: Route queries to the right search strategy, execute hybrid search, rerank, resolve citations.

### New File: `backend/app/services/retrieval_pipeline.py`

### Stage 1 — Query Router
- Parse query for:
  - **Language** (langdetect or regex heuristics for en/fr/ar)
  - **Legal topics** (keywords → deterministic section injection):
    - "penalty clause", "liquidated damages" → inject Section 27 / relevant articles
    - "termination", "breach" → inject termination clauses
    - "non-compete", "restrictive covenant" → inject Section 27
  - **Document scope** — if user references a specific document name, add metadata filter
- Returns: `QueryPlan(languages, mandatory_sections=[...], metadata_filters={...})`

### Stage 2 — Cross-Lingual Balanced Retrieval
- For each language in QueryPlan.languages:
  - Retrieve top_k/3 chunks from that language subset
- Merge all results (deduplicate by chunk_id)
- Total candidates: ~top_k (capped at 20 before reranker)

### Stage 3 — Hybrid Search (Dense + Sparse)
- For each partition (single user_id), run:
  - ANN on dense_vector (IVF_FLAT, metric: IP since embeddings are normalized)
  - ANN on sparse_vector (SPARSE_INVERTED_INDEX)
- RRF merge (k=60)

### Stage 4 — Knowledge-Layer Injection
- For each `mandatory_section` from QueryPlan:
  - If not already in retrieved results, perform a direct lookup:
    - Milvus query filter: `section_title LIKE "%Section 27%" AND user_id == {user_id}`
  - Inject the found chunk(s) at rank 0 (always included)

### Stage 5 — FlashRank Reranker
- Loads `ms-marco-MiniLM-L-12-v2` (~34MB) on first call
- Reranks ALL candidates (retrieved + injected) against the original query
- Returns top_k (default 5) reranked results

### Stage 6 — Score Threshold Abstention
- If best reranker score < 0.4 → return empty results (system will say "I don't have sufficient information")
- If any mandatory section was requested but not found → warn in metadata

### Stage 7 — Citation Resolver
- For each result chunk, resolve:
  - `[Source 1]` → `{page_number, section_title, text_snippet}`
  - Pass as structured metadata alongside context

---

## Phase 6 — Real Chat Endpoint (RAG Pipeline)

**Goal**: Replace the mock SSE streaming endpoint with real RAG → LLM → SSE streaming.

### Changes to: `backend/app/api/v1/router_chat.py`

- On chat message:
  1. Call `retrieval_pipeline.run(query, user_id)` → returns context chunks + citations
  2. If no context (abstention): stream `{"type": "error", "content": "I don't have sufficient information to answer this question based on the available documents."}`
  3. If context exists:
     - Build system prompt with:
       - Retrieved context (formatted with `[Source N]` markers)
       - Citation instruction: "For each factual claim, cite the source as [Source N]. List sources at the end."
       - Knowledge-layer sections (injected)
     - Call `llm_service.resolve_active_model("generation")` for provider/model
     - Stream tokens via SSE (existing SSE infrastructure)
     - After generation completes: run **citation coverage check**

### Citation Coverage Check
- Parse response for `[Source N]` patterns
- Count paragraphs WITH and WITHOUT citations
- If uncited paragraphs > 30% of total → warn user: "Some statements in this response could not be verified against your documents."

### Citation Metadata
- Return `citations: [{source_index: N, page: X, section: "Y", text: "..."}]` in the final SSE message
- Frontend uses this to render highlights

---

## Phase 7 — Frontend Integration

**Goal**: Wire citations into the chat UI and PDF viewer.

### Changes to: `frontend/src/store/useChatStore.ts`
- Ensure `ChatMessage.citations` is typed properly (`CitationGeometry[]` already exists)
- Store `citations` alongside each assistant message

### Changes to: `frontend/src/components/features/document/DocumentPane.tsx`
- When user clicks a `[Source N]` link in chat:
  - Scroll PDF to the cited `page_number`
  - Highlight the cited text area (using existing `react-pdf` infrastructure)

### Changes to: Chat message rendering
- Render `[Source N]` as clickable links (styled badges)
- On click → emit event that DocumentPane listens to

### Error/Empty States
- When `abstention` returns: show info banner "No relevant documents found for this query"
- When `citation_coverage` warns: show subtle warning banner
- Loading state during RAG pipeline (already exists from SSE)

---

## Phase 8 — Polish & Edge Cases

**Goal**: Handle production edge cases, error recovery, and performance optimization.

### Edge Cases
- **No documents ingested**: graceful message, not crash
- **Query in unsupported language**: route to generation-only (no retrieval) with a note
- **Milvus connection drop**: retry (3 attempts, exponential backoff)
- **Model load failure**: cache the error, don't retry every request
- **Concurrent uploads**: ensure per-user serialization for partition creation

### Performance
- Warm up BGE-M3 on server start (background task)
- Batch chunk encoding during ingestion
- Connection pooling for Milvus
- LRU cache for FlashRank model (already singleton, just ensure no reload)

### Testing
- Unit tests for: chunking boundary cases, query router, citation resolution
- Integration test: upload → query → verify result contains correct citations
- Test abstention threshold with poor-quality chunks

---

## Implementation Order & Dependencies

```
Phase 0 (deps + baseline)
  ↓
Phase 1 (embedding service) ──────────────────────┐
Phase 2 (Milvus client + vector store service) ────┤
Phase 3 (chunking service) ────────────────────────┤
  ↓                                                  ↓
Phase 4 (ingestion pipeline — wires 1+2+3 together)
  ↓
Phase 5 (retrieval pipeline — uses 1+2)
  ↓
Phase 6 (chat endpoint — uses 4+5)
  ↓
Phase 7 (frontend — independent of backend phases)
  ↓
Phase 8 (polish)
```

Phases 1-3 are independent and can be built in parallel.

---

## Key Files Map

| Phase | File | Action |
|-------|------|--------|
| 0 | `backend/requirements.txt` | Add deps |
| 1 | `backend/app/services/embedding_service.py` | New |
| 2 | `backend/app/core/milvus_client.py` | New |
| 2 | `backend/app/services/vector_store_service.py` | New |
| 2 | `backend/app/core/settings.py` | Add Milvus config |
| 3 | `backend/app/services/chunking_service.py` | New |
| 4 | `backend/app/services/pipeline_service.py` | New |
| 4 | `backend/app/api/v1/router_document.py` | Edit |
| 5 | `backend/app/services/retrieval_pipeline.py` | New |
| 6 | `backend/app/api/v1/router_chat.py` | Edit |
| 7 | `frontend/src/store/useChatStore.ts` | Edit |
| 7 | `frontend/src/components/features/document/DocumentPane.tsx` | Edit |
| 8 | Various | Polish |
