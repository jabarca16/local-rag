from __future__ import annotations
import os
import shutil
import threading
from pathlib import Path
from sentence_transformers import SentenceTransformer

CATALOGO: list[dict] = [
    {
        "id": "all-MiniLM-L6-v2",
        "display": "MiniLM L6",
        "cache_folder": "models--sentence-transformers--all-MiniLM-L6-v2",
        "tamanio": "80 MB",
        "calidad_es": "Regular",
        "velocidad_cpu": "Muy rápida",
        "descripcion": "Optimizado para inglés. Ideal si todo el contenido es en inglés.",
        "dims": 384,
    },
    {
        "id": "paraphrase-multilingual-MiniLM-L12-v2",
        "display": "Multilingual L12",
        "cache_folder": "models--sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2",
        "tamanio": "120 MB",
        "calidad_es": "Buena",
        "velocidad_cpu": "Rápida",
        "descripcion": "Multilingüe. Buen balance calidad/velocidad para español.",
        "dims": 384,
    },
    {
        "id": "intfloat/multilingual-e5-small",
        "display": "E5 Small",
        "cache_folder": "models--intfloat--multilingual-e5-small",
        "tamanio": "120 MB",
        "calidad_es": "Muy buena",
        "velocidad_cpu": "Rápida",
        "descripcion": "Multilingüe, mejor calidad que MiniLM con el mismo tamaño.",
        "dims": 384,
    },
    {
        "id": "intfloat/multilingual-e5-base",
        "display": "E5 Base",
        "cache_folder": "models--intfloat--multilingual-e5-base",
        "tamanio": "280 MB",
        "calidad_es": "Excelente",
        "velocidad_cpu": "Moderada",
        "descripcion": "Multilingüe de alta calidad. Recomendado para producción.",
        "dims": 768,
    },
    {
        "id": "BAAI/bge-m3",
        "display": "BGE-M3",
        "cache_folder": "models--BAAI--bge-m3",
        "tamanio": "570 MB",
        "calidad_es": "Excelente",
        "velocidad_cpu": "Lenta",
        "descripcion": "Estado del arte en embeddings multilingües. Máxima calidad.",
        "dims": 1024,
    },
    {
        "id": "paraphrase-multilingual-mpnet-base-v2",
        "display": "Multilingual MPNet",
        "cache_folder": "models--sentence-transformers--paraphrase-multilingual-mpnet-base-v2",
        "tamanio": "280 MB",
        "calidad_es": "Muy buena",
        "velocidad_cpu": "Moderada",
        "descripcion": "Multilingüe sólido basado en MPNet.",
        "dims": 768,
    },
]

CATALOGO_IDS = {m["id"] for m in CATALOGO}
_catalogo_por_id = {m["id"]: m for m in CATALOGO}

_instalando: set[str] = set()


def dims_de(model_id: str) -> int:
    return _catalogo_por_id.get(model_id, {}).get("dims", 384)


def _hf_cache() -> Path:
    hf_home = os.getenv("HF_HOME", os.path.expanduser("~/.cache/huggingface"))
    return Path(hf_home) / "hub"


def esta_instalado(model_id: str) -> bool:
    entry = _catalogo_por_id.get(model_id)
    if not entry:
        return False
    return (_hf_cache() / entry["cache_folder"]).exists()


def estado_de(model_id: str) -> str:
    if model_id in _instalando:
        return "instalando"
    return "instalado" if esta_instalado(model_id) else "disponible"


def listar() -> list[dict]:
    return [{**m, "estado": estado_de(m["id"])} for m in CATALOGO]


def _descargar(model_id: str):
    try:
        SentenceTransformer(model_id)
    finally:
        _instalando.discard(model_id)


def instalar(model_id: str) -> str:
    if model_id not in CATALOGO_IDS:
        return "no_encontrado"
    if esta_instalado(model_id):
        return "instalado"
    if model_id in _instalando:
        return "instalando"
    _instalando.add(model_id)
    threading.Thread(target=_descargar, args=(model_id,), daemon=True).start()
    return "instalando"


def desinstalar(model_id: str, proyectos_activos: list[str]) -> dict:
    if proyectos_activos:
        return {"ok": False, "razon": f"En uso por: {', '.join(proyectos_activos)}"}
    entry = _catalogo_por_id.get(model_id)
    if not entry:
        return {"ok": False, "razon": "Modelo no encontrado en catálogo"}
    ruta = _hf_cache() / entry["cache_folder"]
    if not ruta.exists():
        return {"ok": False, "razon": "Modelo no está instalado"}
    shutil.rmtree(ruta)
    return {"ok": True}
