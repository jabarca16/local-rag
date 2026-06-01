from __future__ import annotations
from sentence_transformers import SentenceTransformer

MODEL_DEFAULT = "paraphrase-multilingual-MiniLM-L12-v2"

_cache: dict[str, SentenceTransformer] = {}


def _get_modelo(nombre_modelo: str) -> SentenceTransformer:
    if nombre_modelo not in _cache:
        _cache[nombre_modelo] = SentenceTransformer(nombre_modelo)
    return _cache[nombre_modelo]


def embeber(textos: list[str], modelo: str = MODEL_DEFAULT) -> list[list[float]]:
    m = _get_modelo(modelo)
    vectores = m.encode(textos, show_progress_bar=False)
    return vectores.tolist()


def embeber_uno(texto: str, modelo: str = MODEL_DEFAULT) -> list[float]:
    return embeber([texto], modelo)[0]
