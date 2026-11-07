"""Calcula embeddings E5 de los chunks tok256 (piloto o corpus completo).

Piloto (subconjunto de documentos, en memoria):
    python -m scripts.embed_chunks \
        --documents data/piloto_documentos_500.parquet \
        --output data/embeddings_piloto_500.parquet

Corpus completo (reanudable, por bloques):
    python -m scripts.embed_chunks --all
  Recorre data/chunks_tok256.parquet en orden y escribe bloques de 20.000 chunks en
  data/embeddings_bloques/bloque_NNNNN.parquet. Un bloque existente nunca se
  sobrescribe: se valida (mismos chunk_id) y se salta, de modo que volver a ejecutar
  reanuda donde quedó. Al final une los bloques en
  data/embeddings_corpus_completo.parquet y verifica el resultado.

Carga el encoder solo desde la caché local (sin conexión), en CPU, con el prefijo
"passage: ", normalización L2 y lotes de 32. No imprime texto de documentos.
"""
from __future__ import annotations

import argparse
import json
import os
import resource
import sys
import threading
import time
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

MODEL = "intfloat/multilingual-e5-small"
DIM = 384
PASSAGE_PREFIX = "passage: "
FULL_CORPUS_CHUNKS = 577324

OUTPUT_SCHEMA = pa.schema([
    ("chunk_id", pa.string()),
    ("document_id", pa.string()),
    ("source", pa.string()),
    ("lang", pa.string()),
    ("token_count", pa.int32()),
    ("vector", pa.list_(pa.float32(), DIM)),
])
CHUNK_COLUMNS = ["chunk_id", "document_id", "source", "token_count", "text"]


class PeakRSS:
    """Muestrea el RSS del proceso en segundo plano y guarda el máximo."""

    def __init__(self, interval=0.05):
        import psutil

        self._process = psutil.Process()
        self._interval = interval
        self._stop = threading.Event()
        self.peak = self._process.memory_info().rss
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        while not self._stop.is_set():
            self.peak = max(self.peak, self._process.memory_info().rss)
            self._stop.wait(self._interval)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._thread.join()
        self.peak = max(self.peak, self._process.memory_info().rss)


def ru_maxrss_bytes():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == "darwin" else value * 1024


def rss_mb():
    import psutil

    return round(psutil.Process().memory_info().rss / 2**20, 1)


def load_encoder(model_name=MODEL):
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(model_name, device="cpu", local_files_only=True)
    hidden = model[0].auto_model.config.hidden_size
    if hidden != DIM:
        raise SystemExit(f"hidden_size inesperado: {hidden} (se esperaba {DIM})")
    return model, hidden


def encode(model, texts, batch_size):
    return model.encode(
        [PASSAGE_PREFIX + t for t in texts],
        batch_size=batch_size,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    ).astype(np.float32)


def to_table(chunk_ids, document_ids, sources, langs, token_counts, vectors):
    return pa.Table.from_arrays(
        [
            pa.array(chunk_ids, pa.string()),
            pa.array(document_ids, pa.string()),
            pa.array(sources, pa.string()),
            pa.array(langs, pa.string()),
            pa.array(token_counts, pa.int32()),
            pa.FixedSizeListArray.from_arrays(pa.array(vectors.reshape(-1), pa.float32()), DIM),
        ],
        schema=OUTPUT_SCHEMA,
    )


def verify(vectors, chunk_ids):
    norms = np.linalg.norm(vectors, axis=1)
    return {
        "dim": int(vectors.shape[1]),
        "chunk_ids_unique": len(set(chunk_ids)) == len(chunk_ids),
        "nan": int(np.isnan(vectors).sum()),
        "norm_min": float(norms.min()),
        "norm_max": float(norms.max()),
        "norm_ok": bool(np.allclose(norms, 1.0, atol=1e-3)),
    }


def checks_ok(checks):
    return checks["chunk_ids_unique"] and checks["nan"] == 0 and checks["norm_ok"] and checks["dim"] == DIM


# ── Piloto ───────────────────────────────────────────────────────────────────
def select_chunks(chunks_path, documents_path):
    docs = pq.read_table(documents_path, columns=["document_id", "lang"])
    lang = dict(zip(docs["document_id"].to_pylist(), docs["lang"].to_pylist()))
    ids = pa.array(list(lang), pa.string())
    table = pq.read_table(
        chunks_path,
        columns=["chunk_id", "document_id", "chunk_index", "source", "token_count", "text"],
        filters=pc.is_in(pc.field("document_id"), value_set=ids),
    )
    table = table.sort_by([("document_id", "ascending"), ("chunk_index", "ascending")])
    langs = pa.array([lang[d] for d in table["document_id"].to_pylist()], pa.string())
    return table.append_column("lang", langs), len(lang)


def run_subset(args):
    output = Path(args.output)
    if output.exists():
        raise SystemExit(f"La salida ya existe; no se sobrescribe: {output}")
    import torch

    model, hidden = load_encoder()
    table, n_docs = select_chunks(args.chunks, args.documents)
    chunk_ids = table["chunk_id"].to_pylist()

    with PeakRSS() as rss:
        start = time.perf_counter()
        vectors = encode(model, table["text"].to_pylist(), args.batch_size)
        elapsed = time.perf_counter() - start

    checks = verify(vectors, chunk_ids)
    if not checks_ok(checks):
        raise SystemExit(f"Verificación fallida: {checks}")
    out = to_table(chunk_ids, table["document_id"].to_pylist(), table["source"].to_pylist(),
                   table["lang"].to_pylist(), table["token_count"].to_pylist(), vectors)
    pq.write_table(out, output, compression="zstd")

    n = len(chunk_ids)
    per_chunk = elapsed / n
    print(json.dumps({
        "model": MODEL, "hidden_size": hidden, "device": "cpu",
        "torch_threads": torch.get_num_threads(), "batch_size": args.batch_size,
        "documents": n_docs, "chunks": n, "seconds_total": round(elapsed, 2),
        "ms_per_chunk": round(per_chunk * 1000, 2), "chunks_per_second": round(n / elapsed, 1),
        "peak_rss_mb_during_encode": round(rss.peak / 2**20, 1),
        "ru_maxrss_mb_process": round(ru_maxrss_bytes() / 2**20, 1),
        "estimate_full_corpus_hours": round(per_chunk * FULL_CORPUS_CHUNKS / 3600, 2),
        "checks": checks, "output": str(output), "output_bytes": output.stat().st_size,
    }, ensure_ascii=False, indent=1))


# ── Corpus completo por bloques ──────────────────────────────────────────────
def iter_blocks(chunks_path, block_size):
    """Divide el Parquet de chunks, en su orden, en bloques exactos de block_size filas."""
    buffer = []
    for batch in pq.ParquetFile(chunks_path).iter_batches(columns=CHUNK_COLUMNS, batch_size=4096):
        buffer.extend(batch.to_pylist())
        while len(buffer) >= block_size:
            yield buffer[:block_size]
            buffer = buffer[block_size:]
    if buffer:
        yield buffer


def block_path(blocks_dir, index):
    return Path(blocks_dir) / f"bloque_{index:05d}.parquet"


def log(event, **fields):
    print(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "event": event, **fields},
                     ensure_ascii=False), flush=True)


def write_once(table, path):
    """Escribe en un temporal y lo publica sin sobrescribir un bloque existente."""
    tmp = path.with_suffix(".parquet.tmp")
    pq.write_table(table, tmp, compression="zstd")
    try:
        os.link(tmp, path)  # falla si path ya existe: nunca sobrescribe
    finally:
        tmp.unlink()


def run_all(args):
    import torch

    blocks_dir = Path(args.blocks_dir)
    blocks_dir.mkdir(parents=True, exist_ok=True)
    output = Path(args.output)
    if output.exists():
        raise SystemExit(f"La salida ya existe; no se sobrescribe: {output}")
    total_rows = pq.ParquetFile(args.chunks).metadata.num_rows
    n_blocks = -(-total_rows // args.block_size)

    docs = pq.read_table(args.lang_source, columns=["document_id", "lang"])
    lang = dict(zip(docs["document_id"].to_pylist(), docs["lang"].to_pylist()))
    del docs
    model, hidden = load_encoder()
    log("inicio", chunks=total_rows, block_size=args.block_size, blocks=n_blocks,
        hidden_size=hidden, torch_threads=torch.get_num_threads(), rss_mb=rss_mb())

    started = time.perf_counter()
    done = encoded = 0
    for index, rows in enumerate(iter_blocks(args.chunks, args.block_size)):
        path = block_path(blocks_dir, index)
        ids = [r["chunk_id"] for r in rows]
        if path.exists():
            existing = pq.read_table(path, columns=["chunk_id"])["chunk_id"].to_pylist()
            if existing != ids:
                raise SystemExit(f"{path.name} existe pero no coincide con los chunks esperados.")
            done += len(rows)
            log("bloque_existente", bloque=index, filas=len(rows), procesados=done, total=total_rows)
            continue
        missing_lang = sum(1 for r in rows if r["document_id"] not in lang)
        if missing_lang:
            raise SystemExit(f"{missing_lang} chunks del bloque {index} no tienen lang.")
        with PeakRSS() as rss:
            t0 = time.perf_counter()
            vectors = encode(model, [r["text"] or "" for r in rows], args.batch_size)
            seconds = time.perf_counter() - t0
        checks = verify(vectors, ids)
        if not checks_ok(checks):
            raise SystemExit(f"Bloque {index} no pasa la verificación: {checks}")
        write_once(to_table(ids, [r["document_id"] for r in rows], [r["source"] for r in rows],
                            [lang[r["document_id"]] for r in rows],
                            [r["token_count"] for r in rows], vectors), path)
        done += len(rows)
        encoded += len(rows)
        elapsed = time.perf_counter() - started
        rate = encoded / elapsed if elapsed else 0.0
        log("bloque", bloque=index, de=n_blocks, filas=len(rows), segundos=round(seconds, 1),
            ms_por_chunk=round(seconds / len(rows) * 1000, 2), procesados=done, total=total_rows,
            rss_pico_mb=round(rss.peak / 2**20, 1),
            eta_min=round((total_rows - done) / rate / 60, 1) if rate else None)

    if done != total_rows:
        raise SystemExit(f"Se procesaron {done} chunks; se esperaban {total_rows}.")
    merge_and_verify(blocks_dir, n_blocks, output, args.expected)
    log("fin", segundos_sesion=round(time.perf_counter() - started, 1),
        ru_maxrss_mb=round(ru_maxrss_bytes() / 2**20, 1))


def merge_and_verify(blocks_dir, n_blocks, output, expected):
    tmp = output.with_suffix(".parquet.tmp")
    seen = set()
    rows = nan = 0
    norm_min, norm_max = float("inf"), float("-inf")
    with pq.ParquetWriter(tmp, OUTPUT_SCHEMA, compression="zstd") as writer:
        for index in range(n_blocks):
            table = pq.read_table(block_path(blocks_dir, index))
            if table.schema != OUTPUT_SCHEMA:
                raise SystemExit(f"Esquema inesperado en el bloque {index}.")
            vectors = table["vector"].combine_chunks().flatten().to_numpy().reshape(-1, DIM)
            norms = np.linalg.norm(vectors, axis=1)
            nan += int(np.isnan(vectors).sum())
            norm_min, norm_max = min(norm_min, float(norms.min())), max(norm_max, float(norms.max()))
            seen.update(table["chunk_id"].to_pylist())
            rows += table.num_rows
            writer.write_table(table)
    result = {
        "filas": rows, "esperadas": expected, "chunk_ids_unicos": len(seen) == rows,
        "nan": nan, "norma_min": norm_min, "norma_max": norm_max, "dim": DIM,
    }
    ok = (rows == expected and result["chunk_ids_unicos"] and nan == 0
          and abs(norm_min - 1) < 1e-3 and abs(norm_max - 1) < 1e-3)
    if not ok:
        log("verificacion_fallida", **result)
        raise SystemExit("La unión no pasa la verificación; se conserva el temporal para revisión.")
    os.link(tmp, output)
    tmp.unlink()
    log("union", salida=str(output), bytes=output.stat().st_size, **result)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--chunks", default="data/chunks_tok256.parquet")
    parser.add_argument("--documents", default="data/piloto_documentos_500.parquet",
                        help="Modo piloto: documentos a incluir.")
    parser.add_argument("--output", default=None)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--all", action="store_true", help="Corpus completo por bloques, reanudable.")
    parser.add_argument("--blocks-dir", default="data/embeddings_bloques")
    parser.add_argument("--block-size", type=int, default=20000)
    parser.add_argument("--lang-source", default="data/documentos_rag.parquet",
                        help="Modo --all: Parquet con document_id y lang.")
    parser.add_argument("--expected", type=int, default=FULL_CORPUS_CHUNKS)
    args = parser.parse_args()

    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    if args.all:
        args.output = args.output or "data/embeddings_corpus_completo.parquet"
        run_all(args)
    else:
        args.output = args.output or "data/embeddings_piloto_500.parquet"
        run_subset(args)


if __name__ == "__main__":
    main()
