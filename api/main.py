import os
from dotenv import load_dotenv
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from api.routes import ingest, query, docs, login, proyectos, modelos, jobs
from mcp_local.sse_app import mcp_app
from api.auth import validar_token, validar_token_o_service_key
from ingesta.indexer import stats as _stats

load_dotenv()

app = FastAPI(title="LocalRAG API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Público: solo login
app.include_router(login.router)

# Acceso dual (JWT o service key): solo endpoints de lectura para agentes MCP
app.include_router(query.router, dependencies=[Depends(validar_token_o_service_key)])

# Protegidos solo con JWT: ingesta, gestión y operaciones destructivas
app.include_router(ingest.router, dependencies=[Depends(validar_token)])
app.include_router(docs.router, dependencies=[Depends(validar_token)])
app.include_router(proyectos.router, dependencies=[Depends(validar_token)])
app.include_router(modelos.router, dependencies=[Depends(validar_token)])

# Acceso dual (JWT o service key): estado de jobs async
app.include_router(jobs.router, dependencies=[Depends(validar_token_o_service_key)])

# MCP sobre SSE (acceso remoto para Claude web y agentes)
app.mount("/mcp", mcp_app)

# Portal admin servido como archivos estáticos
app.mount("/portal", StaticFiles(directory="portal", html=True), name="portal")


@app.get("/stats", dependencies=[Depends(validar_token_o_service_key)])
def estadisticas():
    return _stats()


@app.get("/")
def raiz():
    return {"status": "ok", "version": "1.0.0"}
