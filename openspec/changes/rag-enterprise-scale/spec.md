# Spec: RAG Enterprise-Scale Refactor

## Capabilities

| Capability | Type | Spec File |
|------------|------|-----------|
| vector-store | New | specs/vector-store/spec.md |
| async-ingestion | New | specs/async-ingestion/spec.md |
| mcp-tenant-scoping | New | specs/mcp-tenant-scoping/spec.md |

## Requirement Summary

| Domain | Requirements | Scenarios |
|--------|-------------|-----------|
| vector-store | 3 | 10 |
| async-ingestion | 4 | 12 |
| mcp-tenant-scoping | 5 | 11 |
| **Total** | **12** | **33** |

## Coverage

- Happy paths: covered across all three domains
- Edge cases: Qdrant unreachable, worker down, missing volume, missing/invalid header, unknown job_id
- Error states: HTTP 400 (missing header), HTTP 404 (unknown job), task `failed` status, tool-not-found

## Sequencing Constraint

`vector-store` MUST be implemented before `mcp-tenant-scoping`. `async-ingestion` is independent and may proceed in parallel.
