import os
import uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from ingesta.crawler import escanear
from ingesta.proyectos import tags_de, modelo_de
from ingesta.embedder import MODEL_DEFAULT
from worker.tasks import ingestar_archivo_task, ingestar_urls_task

router = APIRouter(prefix="/ingest", tags=["ingesta"])

UPLOADS_DIR = "/tmp/uploads"


class ScanRequest(BaseModel):
    url: str
    profundidad: int = 2


class DownloadRequest(BaseModel):
    urls: list[str]
    proyecto: str = ""
    tags: list[str] = []


@router.post("/file", status_code=202)
async def ingestar_archivo(
    file: UploadFile = File(...),
    proyecto: str = Form(default=""),
    tags: str = Form(default=""),
):
    ext = Path(file.filename).suffix.lower()
    if ext not in (".pdf", ".txt", ".docx"):
        raise HTTPException(status_code=400, detail=f"Formato no soportado: {ext}")

    tags_lista = tags_de(proyecto) if proyecto else []
    modelo = modelo_de(proyecto) if proyecto else MODEL_DEFAULT

    tmp_id = str(uuid.uuid4())
    dest_path = os.path.join(UPLOADS_DIR, f"{tmp_id}_{file.filename}")

    os.makedirs(UPLOADS_DIR, exist_ok=True)
    with open(dest_path, "wb") as fh:
        fh.write(await file.read())

    result = ingestar_archivo_task.delay(
        dest_path,
        proyecto,
        modelo,
        file.filename,
        tags_lista,
    )

    return {"job_id": result.id, "status": "queued"}


@router.post("/crawl/scan")
def crawl_scan(body: ScanRequest):
    urls = escanear(body.url, body.profundidad)
    return {"url_base": body.url, "urls_encontradas": urls, "total": len(urls)}


@router.post("/crawl/download", status_code=202)
def crawl_download(body: DownloadRequest):
    if not body.urls:
        raise HTTPException(status_code=400, detail="Lista de URLs vacía")

    tags = tags_de(body.proyecto) if body.proyecto else []
    modelo = modelo_de(body.proyecto) if body.proyecto else MODEL_DEFAULT

    result = ingestar_urls_task.delay(
        body.urls,
        body.proyecto,
        modelo,
        tags,
    )

    return {"job_id": result.id, "status": "queued"}
