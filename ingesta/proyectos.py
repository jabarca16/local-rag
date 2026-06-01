import json
import os
from pathlib import Path
from ingesta.embedder import MODEL_DEFAULT

_RUTA = Path(os.getenv("PROYECTOS_PATH", "./data/proyectos.json"))


def _cargar() -> dict:
    if not _RUTA.exists():
        return {}
    return json.loads(_RUTA.read_text(encoding="utf-8"))


def _guardar(data: dict):
    _RUTA.parent.mkdir(parents=True, exist_ok=True)
    _RUTA.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def listar() -> list[dict]:
    data = _cargar()
    return [
        {"nombre": k, "tags": v["tags"], "descripcion": v.get("descripcion", ""), "model": v.get("model", MODEL_DEFAULT)}
        for k, v in data.items()
    ]


def obtener(nombre: str) -> dict | None:
    data = _cargar()
    if nombre not in data:
        return None
    return {"nombre": nombre, **data[nombre]}


def crear(nombre: str, tags: list[str], descripcion: str = "", model: str = MODEL_DEFAULT) -> dict:
    data = _cargar()
    data[nombre] = {"tags": tags, "descripcion": descripcion, "model": model}
    _guardar(data)
    return obtener(nombre)


def actualizar(nombre: str, tags: list[str], descripcion: str = "") -> dict | None:
    data = _cargar()
    if nombre not in data:
        return None
    # model se preserva — no se permite cambiar una vez creado el proyecto
    data[nombre] = {"tags": tags, "descripcion": descripcion, "model": data[nombre].get("model", MODEL_DEFAULT)}
    _guardar(data)
    return obtener(nombre)


def eliminar(nombre: str) -> bool:
    data = _cargar()
    if nombre not in data:
        return False
    del data[nombre]
    _guardar(data)
    return True


def tags_de(nombre: str) -> list[str]:
    data = _cargar()
    return data.get(nombre, {}).get("tags", [])


def modelo_de(nombre: str) -> str:
    data = _cargar()
    return data.get(nombre, {}).get("model", MODEL_DEFAULT)
