"""API FastAPI del asistente RAG: /health, /retrieve y /ask.

La lógica vive en app/rag.py; aquí solo se validan entradas y se traducen errores.
Configuración por variables de entorno (ver Settings.from_env en app/rag.py).
"""
from dataclasses import replace
from functools import lru_cache
from typing import Literal

import requests
from fastapi import FastAPI, HTTPException
from pydantic import AliasChoices, BaseModel, Field

from app import rag, solr_backend

app = FastAPI(title="Asistente RAG - Milvus + LLM locales")


@lru_cache(maxsize=1)
def settings():
    return rag.Settings.from_env()


def _settings_or_500():
    try:
        return settings()
    except rag.ConfigError as exc:
        raise HTTPException(500, detail={"servicio": "configuracion", "error": str(exc)})


class RetrieveRequest(BaseModel):
    # Se acepta también "query" por compatibilidad con app/frontend.py.
    question: str = Field(min_length=3, validation_alias=AliasChoices("question", "query"))
    k: int | None = Field(default=None, ge=1, le=15)
    # Motor de recuperación: "milvus" (denso, por defecto) o "solr" (léxico BM25).
    backend: Literal["milvus", "solr"] = "milvus"


class AskRequest(RetrieveRequest):
    model: str | None = None


@app.get("/health")
def health(deep: bool = False):
    """Sin parámetros: la API está viva (healthcheck de Docker).
    Con ?deep=true: prueba Milvus (colección y filas) y Ollama (modelos descargados)."""
    if not deep:
        return {"status": "ok"}
    s = _settings_or_500()
    out = {"status": "ok", "collection": s.collection, "prompt": f"{rag.PROMPT_NAME} v{rag.PROMPT_VERSION}"}
    try:
        client = rag._milvus_client(s)
        exists = client.has_collection(s.collection)
        # count(*) con lectura fuerte: get_collection_stats incluye filas reemplazadas por upsert
        # hasta la compactación y puede sobrecontar.
        rows = int(client.query(collection_name=s.collection, filter="", output_fields=["count(*)"],
                                consistency_level="Strong")[0]["count(*)"]) if exists else 0
        out["milvus"] = {"ok": exists, "exists": exists, "rows": rows}
        if not exists:
            out["status"] = "degraded"
    except Exception as exc:
        out["milvus"] = {"ok": False, "error": type(exc).__name__}
        out["status"] = "degraded"
    try:
        r = requests.get(f"{s.ollama_url}/api/tags", timeout=5)
        r.raise_for_status()
        pulled = [m["name"] for m in r.json().get("models", [])]
        out["ollama"] = {"ok": True, "models": pulled,
                         "missing": [m for m in s.available_models if m not in pulled]}
    except Exception as exc:
        out["ollama"] = {"ok": False, "error": type(exc).__name__}
        out["status"] = "degraded"
    if solr_backend.habilitado():
        out["solr"] = solr_backend.health()
        if not out["solr"]["ok"]:
            out["status"] = "degraded"
    return out


@app.post("/retrieve")
def retrieve(req: RetrieveRequest):
    s = _settings_or_500()
    k = req.k or s.top_k
    try:
        if req.backend == "solr":
            fragments, coleccion = solr_backend.retrieve(req.question, k), solr_backend.config()["core"]
        else:
            fragments, coleccion = rag.retrieve(req.question, k, s), s.collection
    except rag.MilvusUnavailable as exc:
        raise HTTPException(503, detail={"servicio": "milvus", "error": str(exc)})
    except solr_backend.SolrUnavailable as exc:
        raise HTTPException(503, detail={"servicio": "solr", "error": str(exc)})
    keys = ("chunk_id", "score", "document_id", "source", "lang", "url", "created_at_utc", "text")
    return {"k": k, "backend": req.backend, "collection": coleccion,
            "fragments": [{key: f.get(key) for key in keys} for f in fragments]}


@app.post("/ask")
def ask(req: AskRequest):
    s = _settings_or_500()
    model = req.model or s.default_model
    if model not in s.available_models:
        raise HTTPException(400, detail={"error": f"Modelo no permitido: {model}",
                                         "permitidos": list(s.available_models)})
    kwargs = {}
    if req.backend == "solr":
        # BM25 no es comparable entre consultas: el umbral de abstención por puntuación es propio
        # (SOLR_SCORE_THRESHOLD, 0 = no abstenerse por puntuación). El resto del flujo no cambia.
        cfg = solr_backend.config()
        s = replace(s, collection=f"solr:{cfg['core']}", score_threshold=cfg["threshold"])
        kwargs["retriever"] = lambda q, kk: solr_backend.retrieve(q, kk)
    try:
        out = rag.answer(req.question, s, model=model, k=req.k, **kwargs)
        out["backend"] = req.backend
        return out
    except solr_backend.SolrUnavailable as exc:
        raise HTTPException(503, detail={"servicio": "solr", "error": str(exc)})
    except rag.MilvusUnavailable as exc:
        raise HTTPException(503, detail={"servicio": "milvus", "error": str(exc)})
    except rag.OllamaRepetition as exc:
        # El servicio respondió, pero cortó la generación: 502 y motivo específico.
        raise HTTPException(502, detail={"servicio": "ollama", "motivo": "repeticion", "error": str(exc)})
    except rag.OllamaUnavailable as exc:
        raise HTTPException(503, detail={"servicio": "ollama", "error": str(exc)})
