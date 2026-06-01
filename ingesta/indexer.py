from __future__ import annotations
import logging
import os
import uuid

from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.exceptions import UnexpectedResponse

from ingesta.embedder import embeber, embeber_uno, MODEL_DEFAULT
from ingesta.modelos import dims_de

logger = logging.getLogger(__name__)

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))

_cliente: QdrantClient | None = None


def _get_cliente() -> QdrantClient:
    global _cliente
    if _cliente is None:
        _cliente = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    return _cliente


def _nombre_coleccion(proyecto: str, dims: int) -> str:
    return f"rag_{proyecto}_{dims}"


def _asegurar_coleccion(nombre: str, dims: int) -> None:
    cliente = _get_cliente()
    try:
        cliente.get_collection(nombre)
    except (UnexpectedResponse, Exception):
        cliente.create_collection(
            collection_name=nombre,
            vectors_config=models.VectorParams(size=dims, distance=models.Distance.COSINE),
        )


def _colecciones_rag() -> list[str]:
    """Retorna nombres de todas las colecciones con prefijo rag_."""
    cliente = _get_cliente()
    todas = cliente.get_collections().collections
    return [c.name for c in todas if c.name.startswith("rag_")]


# Startup check — falla en importación si Qdrant no está disponible
try:
    _get_cliente().get_collections()
except Exception as exc:
    logger.error("Qdrant no disponible en %s:%s — %s", QDRANT_HOST, QDRANT_PORT, exc)
    raise SystemExit(1) from exc


def indexar(chunks: list[dict], modelo: str = MODEL_DEFAULT) -> int:
    if not chunks:
        return 0

    dims = dims_de(modelo)

    # Agrupar chunks por proyecto para upsert en colecciones correctas
    por_proyecto: dict[str, list[dict]] = {}
    for chunk in chunks:
        meta = chunk.get("metadata", {})
        proyecto = meta.get("proyecto", "default")
        por_proyecto.setdefault(proyecto, []).append(chunk)

    total = 0
    for proyecto, grupo in por_proyecto.items():
        nombre = _nombre_coleccion(proyecto, dims)
        _asegurar_coleccion(nombre, dims)

        textos = [c["texto"] for c in grupo]
        vectores = embeber(textos, modelo)

        puntos = []
        for chunk, vector in zip(grupo, vectores):
            meta = chunk.get("metadata", {})
            tags = meta.get("tags", [])
            if isinstance(tags, str):
                import json
                try:
                    tags = json.loads(tags)
                except Exception:
                    tags = []
            puntos.append(
                models.PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vector,
                    payload={
                        "texto": chunk["texto"],
                        "fuente": meta.get("fuente", ""),
                        "tipo": meta.get("tipo", ""),
                        "proyecto": proyecto,
                        "tags": tags,
                    },
                )
            )

        _get_cliente().upsert(collection_name=nombre, points=puntos)
        total += len(puntos)

    return total


def buscar(
    query: str,
    n_resultados: int = 5,
    proyecto: str | None = None,
    tags: list[str] | None = None,
    modelo: str = MODEL_DEFAULT,
) -> list[dict]:
    dims = dims_de(modelo)
    vector = embeber_uno(query, modelo)

    # Determinar colecciones a consultar
    if proyecto:
        nombres = [_nombre_coleccion(proyecto, dims)]
    else:
        nombres = _colecciones_rag()

    filtro = None
    if tags:
        filtro = models.Filter(
            must=[
                models.FieldCondition(
                    key="tags",
                    match=models.MatchAny(any=tags),
                )
            ]
        )

    items: list[dict] = []
    for nombre in nombres:
        try:
            respuesta = _get_cliente().query_points(
                collection_name=nombre,
                query=vector,
                limit=n_resultados,
                query_filter=filtro,
                with_payload=True,
            )
        except Exception:
            continue

        for hit in respuesta.points:
            payload = hit.payload or {}
            items.append(
                {
                    "texto": payload.get("texto", ""),
                    "metadata": {
                        "fuente": payload.get("fuente", ""),
                        "tipo": payload.get("tipo", ""),
                        "proyecto": payload.get("proyecto", ""),
                        "tags": payload.get("tags", []),
                    },
                    "distancia": hit.score,
                }
            )

    # Si se consultaron múltiples colecciones, reordenar por score descendente
    if len(nombres) > 1:
        items.sort(key=lambda x: x["distancia"], reverse=True)
        items = items[:n_resultados]

    return items


def listar_documentos(proyecto: str | None = None) -> list[dict]:
    cliente = _get_cliente()

    if proyecto:
        dims_default = dims_de(MODEL_DEFAULT)
        nombre = _nombre_coleccion(proyecto, dims_default)
        nombres = [nombre]
        # También incluir colecciones con otros dims si existen
        todos = _colecciones_rag()
        prefijo = f"rag_{proyecto}_"
        nombres = [n for n in todos if n.startswith(prefijo)]
        if not nombres:
            return []
    else:
        nombres = _colecciones_rag()

    vistos: dict[str, dict] = {}
    for nombre in nombres:
        offset = None
        while True:
            try:
                resultado, siguiente = cliente.scroll(
                    collection_name=nombre,
                    scroll_filter=None,
                    limit=100,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )
            except Exception:
                break

            for punto in resultado:
                payload = punto.payload or {}
                fuente = payload.get("fuente", "desconocido")
                if fuente not in vistos:
                    vistos[fuente] = {
                        "fuente": fuente,
                        "tipo": payload.get("tipo", ""),
                        "proyecto": payload.get("proyecto", ""),
                        "tags": payload.get("tags", []),
                    }

            if siguiente is None:
                break
            offset = siguiente

    return list(vistos.values())


def listar_proyectos() -> list[str]:
    """Retorna lista de cliente_id extraídos de los nombres de colecciones rag_."""
    proyectos: set[str] = set()
    for nombre in _colecciones_rag():
        # nombre: rag_{cliente_id}_{dims}
        partes = nombre.split("_")
        # rag + cliente_id + dims → mínimo 3 partes
        if len(partes) >= 3:
            # dims es el último segmento (numérico); cliente_id puede contener _
            cliente_id = "_".join(partes[1:-1])
            if cliente_id:
                proyectos.add(cliente_id)
    return sorted(proyectos)


def eliminar_documento(fuente: str) -> int:
    cliente = _get_cliente()
    total = 0
    for nombre in _colecciones_rag():
        try:
            resultado = cliente.delete(
                collection_name=nombre,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="fuente",
                                match=models.MatchValue(value=fuente),
                            )
                        ]
                    )
                ),
            )
            # Qdrant no devuelve conteo directo en delete; asumimos éxito
            total += 1 if resultado else 0
        except Exception:
            continue
    return total


def actualizar_tags_proyecto(proyecto: str, tags: list[str]) -> int:
    cliente = _get_cliente()
    total = 0
    todos = _colecciones_rag()
    prefijo = f"rag_{proyecto}_"
    nombres = [n for n in todos if n.startswith(prefijo)]

    filtro = models.Filter(
        must=[
            models.FieldCondition(
                key="proyecto",
                match=models.MatchValue(value=proyecto),
            )
        ]
    )

    for nombre in nombres:
        try:
            cliente.overwrite_payload(
                collection_name=nombre,
                payload={"tags": tags},
                points=models.FilterSelector(filter=filtro),
            )
            total += 1
        except Exception:
            continue

    return total


def purgar(proyecto: str | None = None) -> int:
    cliente = _get_cliente()

    if proyecto:
        todos = _colecciones_rag()
        prefijo = f"rag_{proyecto}_"
        nombres = [n for n in todos if n.startswith(prefijo)]
        for nombre in nombres:
            try:
                cliente.delete_collection(nombre)
            except Exception:
                continue
        return len(nombres)

    # Sin proyecto: eliminar todas las colecciones rag_*
    nombres = _colecciones_rag()
    for nombre in nombres:
        try:
            cliente.delete_collection(nombre)
        except Exception:
            continue
    return -1


def stats() -> dict:
    cliente = _get_cliente()
    total = 0
    proyectos: set[str] = set()

    for nombre in _colecciones_rag():
        try:
            info = cliente.get_collection(nombre)
            total += info.points_count or 0
            # Extraer cliente_id del nombre de colección
            partes = nombre.split("_")
            if len(partes) >= 3:
                cliente_id = "_".join(partes[1:-1])
                if cliente_id:
                    proyectos.add(cliente_id)
        except Exception:
            continue

    return {"total_chunks": total, "proyectos": sorted(proyectos)}
