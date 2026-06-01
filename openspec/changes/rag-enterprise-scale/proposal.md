# Proposal: RAG Enterprise-Scale Refactor

## Intent

LocalRAG is being integrated as a multi-tenant component of a SaaS platform. Three blocking gaps exist:

1. **Chroma → Qdrant**: Current single shared collection with `proyecto` metadata filters gives no true isolation — one misconfigured query can leak cross-tenant data. The SaaS context demands hard collection-per-tenant boundaries.
2. **Async ingestion**: Blocking sync handlers hold HTTP connections for the full embed+index duration. Under production load, this exhausts workers and offers no job-status visibility to the platform.
3. **MCP tenant scoping**: `collection_id` is currently optional and caller-controlled — an LLM could forge or omit it. Platform security requires it be injected from the SSE session context, invisible to the model.

All three are pre-requisites before the service can be onboarded to the SaaS platform.

## Scope

### In Scope

- Replace `ingesta/indexer.py` entirely: Chroma client → Qdrant client, same public interface, collection-per-tenant naming `{collection_id}_{dims}`
- Async ingestion pipeline: Celery + Redis; `POST /ingest/file` and `POST /ingest/crawl/download` return `job_id` immediately; new `GET /jobs/{job_id}` polls status
- MCP tenant injection: `X-Collection-Id` header → `contextvars.ContextVar` at SSE session start; `buscar_contexto` reads collection from context, LLM passes `query` only
- Docker Compose from scratch: 4 services — API, Celery worker, Qdrant, Redis; shared `uploads/` volume for file hand-off
- `requirements.txt` update: remove `chromadb`, add `qdrant-client`, `celery`, `redis`

### Out of Scope

- JWT tenant claims (`collection_id` in JWT payload) — deferred; header injection is sufficient for now
- `mcp_local/server.py` (stdio variant) — single-tenant use case, not affected by SaaS migration
- `ingesta/proyectos.py` JSON registry refactor — remains as metadata overlay; authoritative source becomes Qdrant collections
- Automated test suite — no test runner exists; validation remains manual smoke tests
- Model download refactor in `ingesta/modelos.py` — threading pattern stays as-is

## Capabilities

> Researched `openspec/specs/` — directory does not yet exist. All capabilities below are new.

### New Capabilities

- `vector-store`: Qdrant-backed indexer with collection-per-tenant isolation, replacing Chroma
- `async-ingestion`: Celery task queue for background embed+index; job status polling via REST
- `mcp-tenant-scoping`: SSE session-bound `collection_id` injection via contextvars; LLM cannot override

### Modified Capabilities

None — no existing specs exist to modify.

## Approach

**Sequential constraint**: Change 1 (Qdrant) must land before Change 3 (MCP tenant scoping) — the MCP scoping relies on collection-per-tenant being real, not metadata filtering. Change 2 (async ingestion) is fully independent and can be spec'd and designed in parallel.

**Qdrant migration**: Full rewrite of `indexer.py` behind the same public interface. Upstream callers (`query.py`, `docs.py`, `proyectos.py`) require zero changes. Qdrant collections created on first use. Point IDs remain `uuid4()` strings — Qdrant accepts them natively.

**Async ingestion**: New `worker/` package. Ingest routes write uploaded file to a shared Docker volume path, dispatch Celery task, return `{job_id, status: "queued"}`. Worker reads file, embeds, indexes, updates Celery result backend (Redis). Jobs route reads `AsyncResult`.

**MCP tenant scoping**: Custom ASGI middleware on the SSE endpoint extracts `X-Collection-Id`, sets a `contextvars.ContextVar` before the request enters FastMCP. Tool function reads from context var — no `proyecto` param exposed to the LLM.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `ingesta/indexer.py` | Replaced | Full rewrite, same public interface |
| `mcp_local/sse_app.py` | Modified | Add middleware for collection_id injection via contextvars |
| `api/routes/ingest.py` | Modified | Sync handlers → async dispatch, return job_id |
| `api/main.py` | Modified | Include jobs router |
| `requirements.txt` | Modified | Remove chromadb, add qdrant-client + celery + redis |
| `docker-compose.yml` | New | API + worker + Qdrant + Redis + volume mounts |
| `worker/celery_app.py` | New | Celery app pointing to Redis broker |
| `worker/tasks.py` | New | indexar_archivo_task, indexar_urls_task |
| `api/routes/jobs.py` | New | GET /jobs/{job_id} → Celery AsyncResult |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| No test suite — regressions invisible | High | Manual smoke-test checklist per capability before merging |
| Celery worker loads model per process (120-570 MB each) | Med | Set `--concurrency=1` on worker; use preload hook if needed |
| File hand-off API → worker silently fails if volume missing | Med | docker-compose.yml must define named volume mounted on both services; verify at startup |
| `proyectos.json` registry diverges from Qdrant collections | Low | Keep JSON as metadata overlay; never use it as existence gate |
| FastMCP context injection breaks on version update | Low | Pin FastMCP version in requirements; document the middleware pattern |

## Rollback Plan

- **Qdrant**: `ingesta/indexer.py` is the sole Chroma consumer. Git revert restores Chroma immediately. Data loss risk: any documents indexed post-migration must be re-ingested into Chroma. Keep Chroma `./data/chroma/` volume intact during migration window.
- **Async ingestion**: Routes can be reverted to sync handlers independently of Qdrant. Remove Celery dispatch, reinstate blocking calls. Redis and worker containers can be stopped without affecting API or Qdrant.
- **MCP scoping**: `sse_app.py` middleware removal restores the old optional `proyecto` param behavior. One-file revert.

## Dependencies

- Qdrant OSS (self-hosted, Docker image `qdrant/qdrant`)
- Redis OSS (self-hosted, Docker image `redis:7-alpine`)
- `qdrant-client` Python package
- `celery` + `redis` Python packages
- Docker + Docker Compose v2 on deployment host

## Success Criteria

- [ ] `POST /ingest/file` returns `{job_id, status: "queued"}` within 200ms; `GET /jobs/{job_id}` eventually returns `completed`
- [ ] Two tenants can ingest documents; searching tenant A never returns tenant B documents
- [ ] MCP `buscar_contexto` called without `collection_id` param by LLM returns results scoped to the session's `X-Collection-Id`
- [ ] `docker compose up` brings all 4 services up with no manual steps
- [ ] Existing `/query`, `/docs`, `/proyectos` routes continue working unchanged after Qdrant migration
