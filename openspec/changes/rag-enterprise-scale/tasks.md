# Tasks: RAG Enterprise-Scale Refactor

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 550–750 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1: Infra + Qdrant → PR 2: Async ingestion → PR 3: MCP scoping |
| Delivery strategy | ask-on-risk |
| Chain strategy | pending |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: pending
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Infrastructure + Qdrant migration | PR 1 | Base: main. Includes docker-compose, deps, full indexer rewrite. Self-contained — smoke test immediately. |
| 2 | Async ingestion (Celery + Redis) | PR 2 | Base: PR 1 branch. New worker/ package + jobs route + ingest route changes. Independent of MCP. |
| 3 | MCP tenant scoping | PR 3 | Base: PR 2 branch. Requires PR 1 (Qdrant collections) to exist. Smoke tests verify LLM isolation. |

---

## Phase 1: Infrastructure

- [x] 1.1 Add `qdrant-client`, `celery[redis]`, `redis` to `requirements.txt`; remove `chromadb`. **Spec**: vector-store / self-hosted Qdrant deployment; async-ingestion / infra.
- [x] 1.2 Create `docker-compose.yml` with 4 services (`api`, `worker`, `qdrant`, `redis`), named volumes (`uploads`, `qdrant_data`, `redis_data`), and health checks per design topology. **Spec**: async-ingestion / infra — all 4 services healthy scenario.
- [x] 1.3 Verify `api` and `worker` services both mount `uploads:/tmp/uploads` volume in `docker-compose.yml`. **Spec**: async-ingestion / shared volume missing scenario.
- [x] 1.4 Add `QDRANT_HOST`, `QDRANT_PORT`, `REDIS_URL` env var reads (with defaults) to a shared config location (e.g. top of `ingesta/indexer.py` and `worker/celery_app.py`). **Spec**: vector-store / self-hosted deployment.

## Phase 2: Qdrant Migration

> Can run in parallel with Phase 3.

- [x] 2.1 Rewrite `ingesta/indexer.py`: replace Chroma client with a module-level `QdrantClient` singleton (`_get_cliente()`); implement `_nombre_coleccion(proyecto, dims) → "rag_{proyecto}_{dims}"`; create collection on first use. **Spec**: vector-store / collection-per-tenant isolation — first ingest creates collection.
- [x] 2.2 Implement `indexar(chunks, modelo)` in `ingesta/indexer.py`: embed chunks, build `PointStruct(id=uuid4_str, vector=..., payload={texto, fuente, tipo, tags})`, upsert into `rag_{proyecto}_{dims}`. **Spec**: vector-store / public interface compatibility.
- [x] 2.3 Implement `buscar(query, n_resultados, proyecto, tags, modelo)` in `ingesta/indexer.py`: query only `rag_{proyecto}_{dims}`; apply `MatchAny` tag filter when `tags` is non-empty. **Spec**: vector-store / search is scoped to tenant.
- [x] 2.4 Implement `listar_documentos(proyecto)`, `eliminar_documento(fuente)`, `purgar(proyecto)`, `stats()` in `ingesta/indexer.py` with Qdrant equivalents. **Spec**: vector-store / listar_documentos, eliminar_documento, purgar, stats scenarios.
- [x] 2.5 Preserve `listar_proyectos() → list[str]` stub (returns Qdrant collection names filtered by `rag_` prefix) to keep public interface intact without breaking upstream callers. **Spec**: vector-store / public interface compatibility.
- [x] 2.6 Add startup check in `ingesta/indexer.py`: call `_get_cliente().get_collections()` at import time; log error and raise `SystemExit(1)` if Qdrant is unreachable. **Spec**: vector-store / Qdrant unreachable at startup.

## Phase 3: Async Ingestion

> Can run in parallel with Phase 2.

- [x] 3.1 Create `worker/__init__.py` (empty package marker). **Design**: file changes.
- [x] 3.2 Create `worker/celery_app.py`: `Celery("localrag", broker=REDIS_URL, backend=REDIS_URL)` with `task_serializer="json"` and `result_expires=86400`. **Spec**: async-ingestion / infra — Celery uses Redis broker + backend.
- [x] 3.3 Create `worker/tasks.py`: implement `@shared_task ingestar_archivo_task(ruta, cliente_id, modelo, tags)` — reads file from `/tmp/uploads/`, calls `chunkear_archivo()` + `indexar()`, deletes tmp file, returns summary dict. **Spec**: async-ingestion / worker processes a file ingest task.
- [x] 3.4 Create `worker/tasks.py`: implement `@shared_task ingestar_urls_task(urls, cliente_id, modelo, tags)` — crawls URLs, chunks, indexes. **Spec**: async-ingestion / crawl ingest returns job_id immediately.
- [x] 3.5 Modify `api/routes/ingest.py` `ingestar_archivo`: write uploaded file to `/tmp/uploads/{job_id}_{filename}`, dispatch `ingestar_archivo_task.delay(...)`, return HTTP 202 `{job_id, status: "queued"}`. **Spec**: async-ingestion / file ingest returns job_id immediately (< 200ms).
- [x] 3.6 Modify `api/routes/ingest.py` `crawl_download`: dispatch `ingestar_urls_task.delay(...)`, return HTTP 202 `{job_id, status: "queued"}`. **Spec**: async-ingestion / crawl ingest returns job_id immediately.
- [x] 3.7 Create `api/routes/jobs.py`: `GET /jobs/{job_id}` reads `AsyncResult(job_id)`; maps Celery states to `queued/processing/completed/failed`; returns HTTP 404 for unknown job_id. **Spec**: async-ingestion / job status polling — all 4 poll scenarios.
- [x] 3.8 Modify `api/main.py`: `include_router(jobs.router)` under the `validar_token_o_service_key` dependency. **Design**: file changes — api/main.py.

## Phase 4: MCP Tenant Scoping

> Depends on Phase 2 completing first.

- [x] 4.1 Add `_collection_ctx: ContextVar[str] = ContextVar("collection_id", default="")` at module level in `mcp_local/sse_app.py`. **Spec**: mcp-tenant-scoping / collection ID injection via header.
- [x] 4.2 In `mcp_local/sse_app.py` `_handle_sse`: extract `X-Collection-Id` header; reject with HTTP 400 if absent or empty; call `_collection_ctx.set(value)` before entering FastMCP run; call `_collection_ctx.reset(token)` in finally block. **Spec**: mcp-tenant-scoping / valid header sets context; missing header is rejected.
- [x] 4.3 Modify `buscar_contexto` signature in `mcp_local/sse_app.py`: remove `proyecto` param; read `cliente_id = _collection_ctx.get()` internally; pass it to `buscar()`. **Spec**: mcp-tenant-scoping / buscar_contexto scoped search; LLM cannot override.
- [x] 4.4 Add `listar_fuentes()` tool to `mcp_local/sse_app.py`: reads `_collection_ctx.get()`, calls `listar_documentos(proyecto=cliente_id)`, returns formatted source list. **Spec**: mcp-tenant-scoping / listar_fuentes returns only session tenant sources.
- [x] 4.5 Remove `listar_proyectos` tool registration from `mcp_local/sse_app.py`. **Spec**: mcp-tenant-scoping / listar_proyectos tool removed — not callable.
- [x] 4.6 Confirm `mcp_local/server.py` (stdio) is untouched — no edits allowed. **Spec**: mcp-tenant-scoping / stdio server unaffected.

## Phase 5: Integration & Smoke Tests

- [ ] 5.1 `docker compose up --build` — verify all 4 services reach healthy state; check `GET http://localhost:6333/healthz` and `redis-cli ping`. **Spec**: async-ingestion / all 4 services healthy.
- [ ] 5.2 Smoke test Qdrant isolation: ingest one file as `cliente_id=acme`, one as `cliente_id=beta`; query each — confirm zero cross-tenant results. **Spec**: vector-store / search is scoped to tenant.
- [ ] 5.3 Smoke test async flow: `POST /ingest/file` → assert HTTP 202 + `job_id`; poll `GET /jobs/{job_id}` until `status=completed`. **Spec**: async-ingestion / file ingest + poll completed job.
- [ ] 5.4 Smoke test job 404: call `GET /jobs/nonexistent-id` → assert HTTP 404. **Spec**: async-ingestion / poll unknown job_id.
- [ ] 5.5 Smoke test MCP header rejection: connect to `/mcp/sse` without `X-Collection-Id` → assert HTTP 400. **Spec**: mcp-tenant-scoping / missing header is rejected.
- [ ] 5.6 Smoke test MCP isolation: open two SSE sessions with different `X-Collection-Id`; call `buscar_contexto` from each — confirm results are scoped per session. **Spec**: mcp-tenant-scoping / search returns only session tenant's results.
- [ ] 5.7 Confirm existing routes unchanged: `GET /query`, `GET /docs`, `GET /proyectos` return valid responses after Qdrant migration. **Spec**: vector-store / public interface compatibility.
