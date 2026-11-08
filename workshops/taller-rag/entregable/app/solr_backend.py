"""Recuperación léxica (BM25) con Apache Solr, como alternativa a Milvus (denso).

Mismo contrato que app/rag.py::retrieve: devuelve fragmentos (chunks) con chunk_id, score,
document_id, source, lang, url, created_at_utc, token_count y text, ordenados por puntuación.
Los chunks son EXACTAMENTE los mismos que se indexan en Milvus (mismo chunk_id): lo escribe
data/ingest_gold.py con --destino solr (o ambos), de modo que la comparación es justa.

Esquema (core de Solr 9, configset _default): id = chunk_id (clave única); document_id, source,
lang, url y created_at_utc como cadenas almacenadas; token_count como entero; el texto va en
text_es (si lang empieza por "es") o en text_en (resto), con el analizador de ese idioma
(minúsculas, stopwords y stemming). La búsqueda usa edismax sobre ambos campos y el BM25 que
Solr trae por defecto.

Configuración por variables de entorno (la define docker-compose.solr.yml):
  SOLR_URL              http://solr:8983/solr
  SOLR_CORE             rag_chunks
  SOLR_SCORE_THRESHOLD  0 (sin abstención por puntuación: BM25 no es comparable entre consultas)
"""
from __future__ import annotations

import os
import re

DEFAULT_URL = "http://solr:8983/solr"
DEFAULT_CORE = "rag_chunks"
CAMPOS_META = ("document_id", "source", "lang", "url", "created_at_utc")
FL = "id,score,document_id,source,lang,url,created_at_utc,token_count,text_es,text_en"
ESPECIALES = re.compile(r'[\\+\-&|!(){}\[\]^"~*?:/]')

CAMPOS_ESQUEMA = [
    {"name": "document_id", "type": "string", "stored": True, "indexed": True},
    {"name": "source", "type": "string", "stored": True, "indexed": True},
    {"name": "lang", "type": "string", "stored": True, "indexed": True},
    {"name": "url", "type": "string", "stored": True, "indexed": False, "docValues": False},
    {"name": "created_at_utc", "type": "string", "stored": True, "indexed": False, "docValues": False},
    {"name": "token_count", "type": "pint", "stored": True, "indexed": False, "docValues": False},
    {"name": "text_es", "type": "text_es", "stored": True, "indexed": True},
    {"name": "text_en", "type": "text_en", "stored": True, "indexed": True},
]


class SolrUnavailable(RuntimeError):
    """Solr no responde, el core no existe o devolvió un error."""


def config():
    return {"url": os.getenv("SOLR_URL", DEFAULT_URL).rstrip("/"),
            "core": os.getenv("SOLR_CORE", DEFAULT_CORE),
            "threshold": float(os.getenv("SOLR_SCORE_THRESHOLD", "0") or 0)}


def habilitado():
    return bool(os.getenv("SOLR_URL", "").strip())


def _http():
    import requests
    return requests


def _llamar(metodo, url, **kw):
    requests = _http()
    try:
        r = requests.request(metodo, url, timeout=kw.pop("timeout", 30), **kw)
    except requests.RequestException as exc:
        raise SolrUnavailable(f"Solr no responde: {type(exc).__name__}") from exc
    if r.status_code >= 400:
        try:
            msg = r.json().get("error", {}).get("msg", "")
        except ValueError:
            msg = ""
        raise SolrUnavailable(f"Solr devolvió HTTP {r.status_code}: {msg[:200]}")
    return r.json()


def limpiar_consulta(pregunta):
    """Quita los caracteres con significado en la sintaxis de Solr para que una pregunta nunca falle."""
    return re.sub(r"\s+", " ", ESPECIALES.sub(" ", pregunta or "")).strip()


# ── Búsqueda ─────────────────────────────────────────────────────────────────
def _a_fragmento(doc):
    texto = doc.get("text_es") or doc.get("text_en") or ""
    if isinstance(texto, list):
        texto = texto[0] if texto else ""
    out = {"chunk_id": doc.get("id"), "score": float(doc.get("score", 0.0)), "text": texto}
    for c in CAMPOS_META:
        v = doc.get(c)
        out[c] = v[0] if isinstance(v, list) and v else v
    tc = doc.get("token_count")
    out["token_count"] = int(tc[0] if isinstance(tc, list) else tc) if tc is not None else None
    return out


def retrieve(question, k, settings=None, url=None, core=None):
    """Top-k chunks por BM25 (edismax sobre text_es y text_en). Mayor puntuación es mejor."""
    c = config()
    url, core = url or c["url"], core or c["core"]
    q = limpiar_consulta(question)
    if not q:
        return []
    body = _llamar("POST", f"{url}/{core}/select", data={
        "q": q, "defType": "edismax", "qf": "text_es text_en", "rows": int(k), "fl": FL, "wt": "json"})
    docs = body.get("response", {}).get("docs", [])
    return sorted((_a_fragmento(d) for d in docs), key=lambda f: f["score"], reverse=True)


# ── Estado ───────────────────────────────────────────────────────────────────
def health(url=None, core=None):
    c = config()
    url, core = url or c["url"], core or c["core"]
    try:
        b = _llamar("GET", f"{url}/{core}/select", params={"q": "*:*", "rows": 0, "wt": "json"}, timeout=10)
        return {"ok": True, "core": core, "rows": int(b["response"]["numFound"])}
    except SolrUnavailable as exc:
        return {"ok": False, "core": core, "error": str(exc)}


def count(url=None, core=None):
    return health(url, core).get("rows", 0)


# ── Indexación ───────────────────────────────────────────────────────────────
def ensure_schema(url=None, core=None):
    """Crea los campos que falten (idempotente). El core debe existir (lo crea solr-precreate)."""
    c = config()
    url, core = url or c["url"], core or c["core"]
    existentes = {f["name"] for f in _llamar("GET", f"{url}/{core}/schema/fields", params={"wt": "json"})["fields"]}
    creados = []
    for campo in CAMPOS_ESQUEMA:
        if campo["name"] not in existentes:
            _llamar("POST", f"{url}/{core}/schema", json={"add-field": campo})
            creados.append(campo["name"])
    return creados


def _recortar(s, n):
    return (s or "")[:n]


def a_documento_solr(chunk):
    lang = (chunk.get("lang") or "").lower()
    doc = {"id": chunk["chunk_id"], "document_id": chunk["document_id"],
           "source": chunk.get("source") or "", "lang": lang,
           "url": _recortar(chunk.get("url"), 2000), "created_at_utc": chunk.get("created_at_utc") or "",
           "token_count": int(chunk.get("token_count") or 0)}
    doc["text_es" if lang.startswith("es") else "text_en"] = chunk.get("text") or ""
    return doc


def index_chunks(chunks, url=None, core=None):
    """Envía un lote (upsert por id: se puede repetir sin duplicar). No hace commit."""
    c = config()
    url, core = url or c["url"], core or c["core"]
    docs = [a_documento_solr(x) for x in chunks]
    if docs:
        _llamar("POST", f"{url}/{core}/update", params={"commit": "false"}, json=docs, timeout=120)
    return len(docs)


def commit(url=None, core=None):
    c = config()
    url, core = url or c["url"], core or c["core"]
    _llamar("POST", f"{url}/{core}/update", params={"commit": "true"}, json=[], timeout=300)
