# MCP Tenant Scoping Specification

## Purpose

Defines session-bound tenant isolation for the SSE MCP server. The `collection_id` MUST be injected from the HTTP connection context and MUST NOT be controllable by the LLM or any tool argument.

## Requirements

### Requirement: Collection ID Injection via Header

The SSE MCP server MUST extract the `X-Collection-Id` header at connection time and store it in a `contextvars.ContextVar`. This value MUST be available to all tool calls within the session. If the header is absent or empty, the connection MUST be rejected with HTTP 400.

#### Scenario: Valid header sets context

- GIVEN an SSE client connects with header `X-Collection-Id: acme`
- WHEN the connection is established
- THEN `collection_id` ContextVar is set to `"acme"` for all tools in that session

#### Scenario: Missing header is rejected

- GIVEN an SSE client connects without the `X-Collection-Id` header
- WHEN the connection attempt is made
- THEN the server responds with HTTP 400
- AND no session is established

#### Scenario: Header value is not overridable by tool arguments

- GIVEN a session with `X-Collection-Id: acme`
- WHEN a tool call is made with any argument that attempts to specify a different collection
- THEN the tool ignores the argument and uses the session's `collection_id` from ContextVar

---

### Requirement: buscar_contexto — Scoped Search Tool

The `buscar_contexto(query, n_resultados=5)` tool MUST accept only `query` and `n_resultados`. It SHALL NOT accept a `proyecto` or `collection_id` parameter. The tool MUST read the `collection_id` from the session ContextVar to scope the search.

#### Scenario: Search returns only session tenant's results

- GIVEN two tenants `acme` and `beta` each have ingested documents
- AND the session's `X-Collection-Id` is `acme`
- WHEN the LLM calls `buscar_contexto(query="factura", n_resultados=5)`
- THEN only documents from collection `acme` are returned
- AND no documents from `beta` appear

#### Scenario: LLM cannot omit collection scope

- GIVEN the session's `X-Collection-Id` is `acme`
- WHEN `buscar_contexto` is called without any collection argument (as designed)
- THEN the search is automatically scoped to `acme`
- AND the LLM receives results without knowing which collection was queried

---

### Requirement: listar_fuentes — Tenant-Scoped Source Listing

The system MUST expose a `listar_fuentes()` MCP tool that lists document sources within the session's collection only. The tool MUST NOT accept any tenant or collection parameter.

#### Scenario: listar_fuentes returns only session tenant sources

- GIVEN the session's `X-Collection-Id` is `acme` with 3 ingested sources
- WHEN the LLM calls `listar_fuentes()`
- THEN exactly the 3 sources belonging to `acme` are returned
- AND sources from other tenants are not included

---

### Requirement: listar_proyectos Tool Removed

The `listar_proyectos` MCP tool MUST NOT exist in the SSE server. A tenant MUST NOT be able to enumerate collections belonging to other tenants.

#### Scenario: listar_proyectos is not callable

- GIVEN a connected SSE MCP session
- WHEN the LLM or client queries the available tools list
- THEN `listar_proyectos` does not appear in the tool registry

#### Scenario: Direct call to removed tool fails

- GIVEN a connected SSE MCP session
- WHEN a client attempts to call `listar_proyectos` directly
- THEN the server responds with a tool-not-found error

---

### Requirement: stdio MCP Server Unaffected

The `mcp_local/server.py` (stdio variant) MUST NOT be modified by this change. Single-tenant local usage remains unchanged.

#### Scenario: stdio server continues to work

- GIVEN the stdio MCP server is started as before
- WHEN any existing tool is called
- THEN behavior is identical to pre-change behavior
