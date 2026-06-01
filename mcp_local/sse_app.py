from __future__ import annotations
import asyncio
import os
from contextvars import ContextVar

from mcp.server.fastmcp import FastMCP
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

from ingesta.indexer import buscar as _buscar, listar_documentos as _listar_documentos
from ingesta.proyectos import modelo_de as _modelo_de

_collection_ctx: ContextVar[str] = ContextVar("collection_id", default="")

mcp = FastMCP("localrag-mcp")


@mcp.tool()
async def buscar_contexto(query: str, n_resultados: int = 5) -> str:
    """Busca información relevante en la base de conocimiento local (RAG)
    para la colección del tenant activo en la sesión actual."""
    cliente_id = _collection_ctx.get()
    if not cliente_id:
        return "No collection_id en sesión. Enviá el header X-Collection-Id."
    modelo = await asyncio.to_thread(_modelo_de, cliente_id)
    resultados = await asyncio.to_thread(_buscar, query, n_resultados, cliente_id, None, modelo)
    if not resultados:
        return "No se encontró información relevante."
    partes = []
    for i, r in enumerate(resultados, 1):
        fuente = r["metadata"].get("fuente", "desconocido")
        partes.append(f"[{i}] Fuente: {fuente}\n{r['texto']}")
    return "\n\n---\n\n".join(partes)


@mcp.tool()
async def listar_fuentes() -> str:
    """Lista las fuentes indexadas en la colección del tenant activo."""
    cliente_id = _collection_ctx.get()
    if not cliente_id:
        return "No collection_id en sesión."
    docs = await asyncio.to_thread(_listar_documentos, cliente_id)
    if not docs:
        return "No hay fuentes indexadas en esta colección."
    return "Fuentes disponibles:\n" + "\n".join(f"- {d.get('fuente', 'desconocido')}" for d in docs)


# ---------------------------------------------------------------------------
# Streamable HTTP transport (compatible con OpenAI y Claude Web)
# ---------------------------------------------------------------------------

_session_manager = StreamableHTTPSessionManager(
    app=mcp._mcp_server,
    stateless=True,
)


async def _handle_mcp(request: Request) -> Response:
    mcp_key = os.getenv("MCP_API_KEY", "")
    if mcp_key:
        key = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        if not key:
            key = request.query_params.get("api_key", "")
        if key != mcp_key:
            return Response("API key inválida", status_code=401)

    collection_id = request.headers.get("X-Collection-Id", "").strip()
    if not collection_id:
        return Response("Header X-Collection-Id requerido", status_code=400)

    token = _collection_ctx.set(collection_id)
    try:
        return await _session_manager.handle_request(request)
    finally:
        _collection_ctx.reset(token)


async def _lifespan(app):
    async with _session_manager.run():
        yield


mcp_app = Starlette(
    lifespan=_lifespan,
    routes=[
        Route("/", endpoint=_handle_mcp, methods=["GET", "POST", "DELETE"]),
        Route("", endpoint=_handle_mcp, methods=["GET", "POST", "DELETE"]),
    ],
)
