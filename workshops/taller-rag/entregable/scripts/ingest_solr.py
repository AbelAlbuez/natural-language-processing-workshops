"""Indexa en Solr los chunks YA existentes de data/chunks_tok256.parquet (corpus completo), tal como están en Milvus.

Los chunk_id, el texto y los metadatos son los mismos que carga scripts/ingest_milvus.py, así que Milvus y Solr
indexan exactamente la misma población (sin la limpieza de relleno; para la versión limpia use data/ingest_gold.py
--limpiar o regenere los chunks). El idioma sale de data/documentos_rag.parquet (columna lang), como en ingest_milvus.py.

Idempotente (upsert por id: se puede repetir). Con Solr en Docker:
  docker compose -f docker-compose.yml -f docker-compose.solr.yml exec -e PYTHONPATH=/work api \
      python -m scripts.ingest_solr --chunks data/chunks_tok256.parquet --documents data/documentos_rag.parquet
Pruebe antes con --limite 5000. Reanudar: --desde N (omite las primeras N filas).
"""
import argparse
import json
import os
import sys
import time

import pyarrow.parquet as pq

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from app import solr_backend as sb  # noqa: E402

COLUMNAS = ["chunk_id", "document_id", "source", "url", "created_at_utc", "token_count", "text"]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--chunks", default="data/chunks_tok256.parquet")
    ap.add_argument("--documents", default="data/documentos_rag.parquet")
    ap.add_argument("--solr-url", default=None, help="por defecto SOLR_URL (http://solr:8983/solr en Docker)")
    ap.add_argument("--solr-core", default=None, help="por defecto SOLR_CORE (rag_chunks)")
    ap.add_argument("--lote", type=int, default=1000, help="chunks por solicitud a Solr")
    ap.add_argument("--limite", type=int, default=None, help="solo las primeras N filas (prueba)")
    ap.add_argument("--desde", type=int, default=0, help="omite las primeras N filas (reanudar)")
    a = ap.parse_args(argv)

    cfg = sb.config()
    url, core = (a.solr_url or cfg["url"]).rstrip("/"), a.solr_core or cfg["core"]
    docs = pq.read_table(a.documents, columns=["document_id", "lang"])
    lang = dict(zip(docs["document_id"].to_pylist(), docs["lang"].to_pylist()))
    pf = pq.ParquetFile(a.chunks)
    total = pf.metadata.num_rows
    objetivo = min(total, a.limite) if a.limite else total
    print(f"chunks en {a.chunks}: {total} · a enviar: {max(objetivo - a.desde, 0)} · destino {url}/{core}", flush=True)
    try:
        print("campos creados:", sb.ensure_schema(url, core) or "ninguno (ya existían)")
        t0, vistos, enviados = time.perf_counter(), 0, 0
        for batch in pf.iter_batches(batch_size=a.lote, columns=COLUMNAS):
            filas = batch.to_pylist()
            if vistos + len(filas) <= a.desde:
                vistos += len(filas)
                continue
            filas = filas[max(a.desde - vistos, 0):]
            vistos += len(batch)
            if a.limite and enviados + max(a.desde, 0) + len(filas) > a.limite:
                filas = filas[: max(a.limite - a.desde - enviados, 0)]
            for r in filas:
                r["lang"] = lang.get(r["document_id"]) or ""
            enviados += sb.index_chunks(filas, url, core)
            if enviados and (enviados // a.lote) % 20 == 0:
                print(f"  {enviados} chunks enviados ({enviados / (time.perf_counter() - t0):.0f}/s)", flush=True)
            if a.limite and a.desde + enviados >= a.limite:
                break
        sb.commit(url, core)
    except sb.SolrUnavailable as exc:
        raise SystemExit(f"Solr: {exc}\n¿Está levantado? docker compose -f docker-compose.yml -f docker-compose.solr.yml up -d")
    print(json.dumps({"solr_core": core, "chunks_enviados": enviados, "filas_en_core": sb.count(url, core),
                      "segundos": round(time.perf_counter() - t0, 1)}))


if __name__ == "__main__":
    main()
