from fastapi import APIRouter
from pydantic import BaseModel
from ingesta.indexer import buscar
from ingesta.proyectos import modelo_de
from ingesta.embedder import MODEL_DEFAULT

router = APIRouter(tags=["consulta"])


class QueryRequest(BaseModel):
    query: str
    n_resultados: int = 5
    proyecto: str | None = None
    tags: list[str] | None = None


@router.post("/query")
def consultar(body: QueryRequest):
    modelo = modelo_de(body.proyecto) if body.proyecto else MODEL_DEFAULT
    resultados = buscar(body.query, body.n_resultados, proyecto=body.proyecto, tags=body.tags, modelo=modelo)
    return {"query": body.query, "proyecto": body.proyecto, "tags": body.tags, "resultados": resultados}
