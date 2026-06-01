import os
from pathlib import Path
from worker.celery_app import celery_app
from ingesta.chunker import chunkear_archivo, chunkear_texto_web
from ingesta.indexer import indexar
from ingesta.crawler import descargar


@celery_app.task(bind=True)
def ingestar_archivo_task(self, file_path: str, cliente_id: str, modelo: str, nombre_original: str, tags: list):
    """
    Reads a file from the shared volume, chunks it, indexes it into Qdrant,
    then deletes the temporary file.
    Returns a summary dict with indexados count and source name.
    """
    ruta = Path(file_path)
    try:
        chunks = chunkear_archivo(
            ruta,
            nombre_original=nombre_original,
            proyecto=cliente_id,
            tags=tags,
        )
        total = indexar(chunks, modelo)
    finally:
        if ruta.exists():
            ruta.unlink(missing_ok=True)

    return {"indexados": total, "fuente": nombre_original}


@celery_app.task(bind=True)
def ingestar_urls_task(self, urls: list, cliente_id: str, modelo: str, tags: list):
    """
    Downloads each URL, chunks the text, and indexes all chunks into Qdrant.
    Returns a summary dict with indexados count and url count.
    """
    paginas = descargar(urls)
    all_chunks = []
    for pagina in paginas:
        chunks = chunkear_texto_web(
            pagina["texto"],
            pagina["url"],
            proyecto=cliente_id,
            tags=tags,
        )
        all_chunks.extend(chunks)

    total = indexar(all_chunks, modelo) if all_chunks else 0
    return {"indexados": total, "urls": len(urls)}
