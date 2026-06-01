from fastapi import APIRouter, HTTPException
from ingesta import modelos as cat
from ingesta import proyectos as mgr

router = APIRouter(prefix="/modelos", tags=["modelos"])


@router.get("")
def listar():
    return {"modelos": cat.listar()}


@router.post("/{model_id:path}/instalar")
def instalar(model_id: str):
    if model_id not in cat.CATALOGO_IDS:
        raise HTTPException(status_code=404, detail="Modelo no encontrado en catálogo")
    estado = cat.instalar(model_id)
    return {"model_id": model_id, "estado": estado}


@router.delete("/{model_id:path}")
def desinstalar(model_id: str):
    proyectos = mgr.listar()
    activos = [p["nombre"] for p in proyectos if p.get("model") == model_id]
    resultado = cat.desinstalar(model_id, activos)
    if not resultado["ok"]:
        raise HTTPException(status_code=400, detail=resultado["razon"])
    return {"ok": True, "model_id": model_id}
