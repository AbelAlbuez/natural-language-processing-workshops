"""Ingesta idempotente de chunks tok256 en Milvus (upsert por chunk_id).

Dos modos:

* Con vectores precalculados (piloto):
      python -m scripts.ingest_milvus --embeddings data/embeddings_piloto_500.parquet
  Toma los vectores del Parquet de embeddings y el texto, la URL y la fecha de
  data/chunks_tok256.parquet, unidos por chunk_id.

* Sin vectores (corpus completo): calcula los embeddings E5 por lotes al vuelo.
      python -m scripts.ingest_milvus
  El idioma de cada chunk se toma de data/documentos_rag.parquet (campo lang).

Volver a ejecutar no duplica filas: upsert reemplaza por clave primaria. Al final se
compara el número de chunk_id de entrada presentes en la colección con el de entrada.
No imprime texto de documentos.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from itertools import islice

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from app.milvus_schema import COLLECTION_NAME, DIM, EMBEDDING_MODEL, VARCHAR_LIMITS, ensure_collection

PASSAGE_PREFIX = "passage: "
CHUNK_COLUMNS = ["chunk_id", "document_id", "source", "url", "created_at_utc", "token_count", "text"]


def batched(iterable, size):
    if size < 1:
        raise ValueError("size debe ser >= 1")
    it = iter(iterable)
    while batch := list(islice(it, size)):
        yield batch


def to_record(chunk, vector, lang):
    """Convierte una fila de chunks_tok256 + vector + idioma en una entidad Milvus."""
    if len(vector) != DIM:
        raise ValueError(f"vector de dimensión {len(vector)}; se esperaba {DIM}")
    record = {
        "chunk_id": str(chunk["chunk_id"]),
        "vector": [float(x) for x in vector],
        "document_id": str(chunk["document_id"]),
        "source": chunk.get("source") or "",
        "lang": lang or "",
        "url": chunk.get("url") or "",
        "created_at_utc": chunk.get("created_at_utc") or "",
        "token_count": int(chunk["token_count"]),
        "text": chunk.get("text") or "",
    }
    for field, limit in VARCHAR_LIMITS.items():
        size = len(record[field].encode("utf-8"))
        if size > limit:
            raise ValueError(f"{field} de {record['chunk_id']} ocupa {size} bytes (> {limit})")
    return record


def upsert_all(client, collection, records, batch_size=256):
    """Inserta por lotes con upsert. Devuelve los chunk_id enviados, en orden."""
    sent = []
    for batch in batched(records, batch_size):
        client.upsert(collection_name=collection, data=batch)
        sent.extend(r["chunk_id"] for r in batch)
    return sent


RETRYABLE = ("lag(", "tsafe", "timeout", "deadline", "not ready")


def query_with_retry(client, attempts=8, wait=15.0, **kwargs):
    """client.query con reintentos ante errores transitorios.

    Tras una carga grande, Milvus puede rechazar lecturas fuertes mientras procesa lo
    recibido ("lag(20.8s) max(3s)"). Se reintenta solo ante esos errores.
    """
    for attempt in range(1, attempts + 1):
        try:
            return client.query(**kwargs)
        except Exception as exc:  # pymilvus.MilvusException y errores de transporte
            if attempt == attempts or not any(k in str(exc).lower() for k in RETRYABLE):
                raise
            time.sleep(wait)


def count_present(client, collection, chunk_ids, batch_size=1000, wait=15.0):
    """Cuántos de los chunk_id dados existen en la colección (lectura fuerte)."""
    found = 0
    for batch in batched(chunk_ids, batch_size):
        rows = query_with_retry(
            client,
            wait=wait,
            collection_name=collection,
            ids=batch,
            output_fields=["chunk_id"],
            consistency_level="Strong",
        )
        found += len(rows)
    return found


def count_total(client, collection, wait=15.0):
    rows = query_with_retry(
        client,
        wait=wait,
        collection_name=collection,
        filter="",
        output_fields=["count(*)"],
        consistency_level="Strong",
    )
    return int(rows[0]["count(*)"])


def records_from_embeddings(embeddings_path, chunks_path, read_batch=20000):
    """Genera entidades leyendo el Parquet de embeddings por lotes de read_batch filas.

    Para cada lote se leen de chunks_path solo los chunk_id de ese lote (texto, URL,
    fecha...). Así la memoria depende del tamaño del lote y no del corpus completo.
    """
    parquet = pq.ParquetFile(embeddings_path)
    if parquet.schema_arrow.field("vector").type.list_size != DIM:
        raise SystemExit("El Parquet de embeddings no tiene vectores de dimensión 384.")

    def generate():
        for batch in parquet.iter_batches(batch_size=read_batch, columns=["chunk_id", "lang", "vector"]):
            ids = batch.column("chunk_id")
            chunks = pq.read_table(
                chunks_path,
                columns=CHUNK_COLUMNS,
                filters=pc.is_in(pc.field("chunk_id"), value_set=ids),
            )
            by_id = {row["chunk_id"]: row for row in chunks.to_pylist()}
            id_list = ids.to_pylist()
            missing = sum(1 for cid in id_list if cid not in by_id)
            if missing:
                raise SystemExit(f"{missing} chunk_id del Parquet de embeddings no están en {chunks_path}.")
            vectors = batch.column("vector").flatten().to_numpy(zero_copy_only=False).reshape(-1, DIM)
            for cid, lang, vector in zip(id_list, batch.column("lang").to_pylist(), vectors):
                yield to_record(by_id[cid], vector, lang)

    return generate(), parquet.metadata.num_rows


def records_with_encoder(chunks_path, documents_path, encode_batch):
    from sentence_transformers import SentenceTransformer

    configured = os.getenv("EMBEDDING_MODEL", EMBEDDING_MODEL)
    if configured != EMBEDDING_MODEL:
        raise SystemExit(f"La colección usa {EMBEDDING_MODEL}; EMBEDDING_MODEL apunta a otro modelo.")
    model = SentenceTransformer(EMBEDDING_MODEL, device="cpu")
    docs = pq.read_table(documents_path, columns=["document_id", "lang"])
    lang = dict(zip(docs["document_id"].to_pylist(), docs["lang"].to_pylist()))
    parquet = pq.ParquetFile(chunks_path)

    def generate():
        for batch in parquet.iter_batches(columns=CHUNK_COLUMNS, batch_size=encode_batch):
            rows = batch.to_pylist()
            vectors = model.encode(
                [PASSAGE_PREFIX + (r["text"] or "") for r in rows],
                batch_size=encode_batch,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            for row, vector in zip(rows, vectors):
                yield to_record(row, vector, lang.get(row["document_id"]))

    return generate(), parquet.metadata.num_rows


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--chunks", default="data/chunks_tok256.parquet")
    parser.add_argument("--embeddings", help="Parquet con vectores precalculados (p. ej. del piloto).")
    parser.add_argument("--documents", default="data/documentos_rag.parquet",
                        help="Fuente del campo lang cuando se calculan los vectores.")
    parser.add_argument("--collection", default=os.getenv("MILVUS_COLLECTION", COLLECTION_NAME))
    parser.add_argument("--batch-size", type=int, default=256, help="Entidades por upsert.")
    parser.add_argument("--encode-batch", type=int, default=32)
    parser.add_argument("--read-batch", type=int, default=20000,
                        help="Filas del Parquet de embeddings leídas por lote.")
    args = parser.parse_args()

    from pymilvus import MilvusClient

    uri = os.getenv("MILVUS_URI")
    if not uri:
        raise SystemExit("Falta la variable de entorno MILVUS_URI.")
    client = MilvusClient(uri=uri)
    created = ensure_collection(client, args.collection)

    start = time.perf_counter()
    if args.embeddings:
        records, expected = records_from_embeddings(args.embeddings, args.chunks, args.read_batch)
    else:
        records, expected = records_with_encoder(args.chunks, args.documents, args.encode_batch)
    sent = upsert_all(client, args.collection, records, args.batch_size)
    if hasattr(client, "flush"):
        client.flush(args.collection)
    client.load_collection(args.collection)

    unique = list(dict.fromkeys(sent))
    present = count_present(client, args.collection, unique)
    report = {
        "collection": args.collection,
        "created": created,
        "mode": "embeddings" if args.embeddings else "encoder",
        "input_rows": expected,
        "sent": len(sent),
        "unique_chunk_ids": len(unique),
        "present_in_collection": present,
        "collection_total": count_total(client, args.collection),
        "seconds": round(time.perf_counter() - start, 1),
    }
    report["ok"] = present == len(unique) == expected
    print(json.dumps(report, ensure_ascii=False))
    if not report["ok"]:
        raise SystemExit("El conteo en Milvus no coincide con la entrada.")


if __name__ == "__main__":
    main()
