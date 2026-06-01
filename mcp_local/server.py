import os
import json
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv("API_URL", "http://localhost:8000")
SERVICE_API_KEY = os.getenv("SERVICE_API_KEY", "")


def _headers() -> dict:
    if SERVICE_API_KEY:
        return {"Authorization": f"Bearer {SERVICE_API_KEY}"}
    return {}


def buscar_contexto(query: str, n_resultados: int = 5, proyecto: str | None = None) -> str:
    try:
        payload = {"query": query, "n_resultados": n_resultados}
        if proyecto:
            payload["proyecto"] = proyecto

        resp = requests.post(f"{API_URL}/query", json=payload, headers=_headers(), timeout=15)
        resp.raise_for_status()
        data = resp.json()
        resultados = data.get("resultados", [])
        if not resultados:
            return "No se encontró información relevante."

        partes = []
        for i, r in enumerate(resultados, 1):
            meta = r["metadata"]
            fuente = meta.get("fuente", "desconocido")
            proj = meta.get("proyecto", "")
            header = f"[{i}] Fuente: {fuente}" + (f" | Proyecto: {proj}" if proj else "")
            partes.append(f"{header}\n{r['texto']}")
        return "\n\n---\n\n".join(partes)

    except Exception as e:
        return f"Error al consultar el RAG: {e}"


def listar_proyectos() -> str:
    try:
        resp = requests.get(f"{API_URL}/stats", headers=_headers(), timeout=10)
        resp.raise_for_status()
        data = resp.json()
        proyectos = data.get("proyectos", [])
        if not proyectos:
            return "No hay proyectos indexados."
        return "Proyectos disponibles:\n" + "\n".join(f"- {p}" for p in proyectos)
    except Exception as e:
        return f"Error al obtener proyectos: {e}"


# ---------------------------------------------------------------------------
# Protocolo MCP sobre stdio (JSON-RPC 2.0)
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "buscar_contexto",
        "description": (
            "Busca información relevante en la base de conocimiento local (RAG). "
            "Usá esta herramienta cuando necesites contexto sobre un tema específico. "
            "Podés filtrar por proyecto para obtener resultados más precisos."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "La pregunta o tema a buscar",
                },
                "proyecto": {
                    "type": "string",
                    "description": "Nombre del proyecto para filtrar la búsqueda (opcional). Usá listar_proyectos para ver los disponibles.",
                },
                "n_resultados": {
                    "type": "integer",
                    "description": "Cantidad de fragmentos a retornar (default: 5)",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "listar_proyectos",
        "description": "Lista todos los proyectos disponibles en la base de conocimiento local.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]


def responder(id_, result=None, error=None):
    msg = {"jsonrpc": "2.0", "id": id_}
    if error:
        msg["error"] = error
    else:
        msg["result"] = result
    print(json.dumps(msg), flush=True)


def manejar(mensaje: dict):
    method = mensaje.get("method")
    id_ = mensaje.get("id")
    params = mensaje.get("params", {})

    if method == "initialize":
        responder(id_, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "localrag-mcp", "version": "1.0.0"},
        })

    elif method == "tools/list":
        responder(id_, {"tools": TOOLS})

    elif method == "tools/call":
        nombre = params.get("name")
        args = params.get("arguments", {})

        if nombre == "buscar_contexto":
            texto = buscar_contexto(
                query=args.get("query", ""),
                n_resultados=args.get("n_resultados", 5),
                proyecto=args.get("proyecto"),
            )
            responder(id_, {"content": [{"type": "text", "text": texto}]})

        elif nombre == "listar_proyectos":
            texto = listar_proyectos()
            responder(id_, {"content": [{"type": "text", "text": texto}]})

        else:
            responder(id_, error={"code": -32601, "message": f"Tool desconocida: {nombre}"})

    else:
        if id_ is not None:
            responder(id_, error={"code": -32601, "message": f"Método desconocido: {method}"})


def main():
    for linea in sys.stdin:
        linea = linea.strip()
        if not linea:
            continue
        try:
            mensaje = json.loads(linea)
            manejar(mensaje)
        except json.JSONDecodeError:
            pass


if __name__ == "__main__":
    main()
