from fastapi import APIRouter, HTTPException
from ingesta.indexer import listar_documentos, eliminar_documento, purgar

router = APIRouter(tags=["documentos"])


@router.get("/index")
def listar(proyecto: str | None = None):
    return {"documentos": listar_documentos(proyecto=proyecto)}



@router.delete("/index/{fuente:path}")
def eliminar(fuente: str):
    eliminados = eliminar_documento(fuente)
    if eliminados == 0:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    return {"fuente": fuente, "chunks_eliminados": eliminados}


@router.delete("/purgar")
def purgar_indice(proyecto: str | None = None):
    total = purgar(proyecto=proyecto)
    if total == -1:
        return {"mensaje": "Índice completo eliminado"}
    return {"mensaje": f"Proyecto '{proyecto}' eliminado", "chunks_eliminados": total}


