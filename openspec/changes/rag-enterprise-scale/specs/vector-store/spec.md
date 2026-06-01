# Vector Store Specification

## Purpose

Defines the Qdrant-backed vector store with hard collection-per-tenant isolation, replacing the Chroma single-collection implementation. The public interface MUST remain identical so upstream callers require zero changes.

## Requirements

### Requirement: Collection-Per-Tenant Isolation

The system MUST store each tenant's vectors in a dedicated Qdrant collection named `{proyecto}_{dims}`, where `proyecto` maps to `cliente_id` and `dims` is the embedding dimension count. Cross-tenant data access MUST be structurally impossible — no shared collection, no metadata filtering as the sole isolation gate.

#### Scenario: First ingest creates collection

- GIVEN Qdrant is running and no collection exists for `proyecto="acme"`
- WHEN `indexar(chunks, modelo)` is called with `proyecto="acme"`
- THEN a Qdrant collection named `acme_{dims}` is created automatically
- AND all chunks are upserted into that collection

#### Scenario: Existing collection reused

- GIVEN collection `acme_768` already exists in Qdrant
- WHEN `indexar(chunks, modelo)` is called again with `proyecto="acme"`
- THEN no new collection is created
- AND chunks are upserted into the existing `acme_768` collection

#### Scenario: Search is scoped to tenant

- GIVEN tenants `acme` and `beta` each have ingested documents
- WHEN `buscar(query, n_resultados, proyecto="acme", tags, modelo)` is called
- THEN only documents from collection `acme_{dims}` are returned
- AND no documents from `beta_{dims}` appear in results

#### Scenario: Qdrant unreachable at startup

- GIVEN Qdrant is not reachable on port 6333
- WHEN the API service starts
- THEN the API MUST log a connection error and fail fast with a non-zero exit code
- AND no ingest or search requests are accepted

---

### Requirement: Public Interface Compatibility

The indexer module MUST expose the same public interface as the current `ingesta/indexer.py`:
`indexar(chunks, modelo)`, `buscar(query, n_resultados, proyecto, tags, modelo)`, `listar_documentos(proyecto)`, `eliminar_documento(fuente)`, `purgar(proyecto)`, `stats()`. No upstream caller (query, docs, proyectos routes) SHALL require any code change.

#### Scenario: listar_documentos returns only tenant documents

- GIVEN tenant `acme` has 3 ingested documents and tenant `beta` has 2
- WHEN `listar_documentos(proyecto="acme")` is called
- THEN exactly 3 documents are returned, all belonging to `acme`

#### Scenario: eliminar_documento removes by source within tenant scope

- GIVEN document with `fuente="file.pdf"` exists in collection `acme_768`
- WHEN `eliminar_documento(fuente="file.pdf")` is called for proyecto `acme`
- THEN the document is deleted from `acme_768`
- AND `beta_768` is not affected

#### Scenario: purgar removes entire tenant collection

- GIVEN collection `acme_768` contains 50 documents
- WHEN `purgar(proyecto="acme")` is called
- THEN collection `acme_768` is deleted from Qdrant
- AND `stats()` no longer reports that collection

#### Scenario: stats returns all tenant collection metrics

- GIVEN three tenant collections exist in Qdrant
- WHEN `stats()` is called
- THEN a summary with per-collection document counts and vector dimensions is returned

---

### Requirement: Self-Hosted Qdrant Deployment

Qdrant MUST run as a self-hosted Docker container accessible at `localhost:6333` (or the configured host). No cloud Qdrant service SHALL be used. The `qdrant-client` Python package MUST be added to `requirements.txt` and `chromadb` MUST be removed.

#### Scenario: Docker Compose starts Qdrant

- GIVEN `docker-compose.yml` defines a `qdrant` service using `qdrant/qdrant` image
- WHEN `docker compose up` is executed
- THEN the Qdrant HTTP API is accessible on port 6333
- AND the Qdrant gRPC port 6334 is optionally exposed

#### Scenario: Qdrant data is persisted across restarts

- GIVEN Qdrant container has ingested collections
- WHEN the container is restarted
- THEN all previously created collections and vectors are still available
