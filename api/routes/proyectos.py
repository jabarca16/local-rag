from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ingesta import proyectos as mgr
from ingesta.indexer import actualizar_tags_proyecto
from ingesta.embedder import MODEL_DEFAULT
from ingesta.modelos import CATALOGO_IDS

router = APIRouter(prefix="/proyectos", tags=["proyectos"])


class ProyectoCreateBody(BaseModel):
    tags: list[str] = []
    descripcion: str = ""
    model: str = MODEL_DEFAULT


class ProyectoUpdateBody(BaseModel):
    tags: list[str] = []
    descripcion: str = ""


@router.get("")
def listar():
    return {"proyectos": mgr.listar()}


@router.get("/{nombre}")
def obtener(nombre: str):
    p = mgr.obtener(nombre)
    if not p:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    return p


@router.post("/{nombre}")
def crear(nombre: str, body: ProyectoCreateBody):
    if mgr.obtener(nombre):
        raise HTTPException(status_code=400, detail="El proyecto ya existe")
    if body.model not in CATALOGO_IDS:
        raise HTTPException(status_code=400, detail=f"Modelo no válido. Opciones: {sorted(CATALOGO_IDS)}")
    return mgr.crear(nombre, body.tags, body.descripcion, body.model)


@router.put("/{nombre}")
def actualizar(nombre: str, body: ProyectoUpdateBody):
    p = mgr.actualizar(nombre, body.tags, body.descripcion)
    if not p:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    actualizar_tags_proyecto(nombre, body.tags)
    return p


@router.delete("/{nombre}")
def eliminar(nombre: str):
    if not mgr.eliminar(nombre):
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    return {"mensaje": f"Proyecto '{nombre}' eliminado"}
