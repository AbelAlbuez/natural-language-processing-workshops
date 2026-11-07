"""Calcula embeddings E5 de los chunks tok256 de un subconjunto de documentos.

Uso (piloto de 500 documentos):
    python -m scripts.embed_chunks \
        --documents data/piloto_documentos_500.parquet \
        --output data/embeddings_piloto_500.parquet

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


def load_encoder(model_name=MODEL):
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(model_name, device="cpu", local_files_only=True)
    hidden = model[0].auto_model.config.hidden_size
    if hidden != DIM:
        raise SystemExit(f"hidden_size inesperado: {hidden} (se esperaba {DIM})")
    return model, hidden


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


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--chunks", default="data/chunks_tok256.parquet")
    parser.add_argument("--documents", default="data/piloto_documentos_500.parquet")
    parser.add_argument("--output", default="data/embeddings_piloto_500.parquet")
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args()

    output = Path(args.output)
    if output.exists():
        raise SystemExit(f"La salida ya existe; no se sobrescribe: {output}")

    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    import torch

    model, hidden = load_encoder()
    table, n_docs = select_chunks(args.chunks, args.documents)
    texts = [PASSAGE_PREFIX + t for t in table["text"].to_pylist()]
    chunk_ids = table["chunk_id"].to_pylist()

    with PeakRSS() as rss:
        start = time.perf_counter()
        vectors = model.encode(
            texts,
            batch_size=args.batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        ).astype(np.float32)
        elapsed = time.perf_counter() - start
    del texts

    checks = verify(vectors, chunk_ids)
    if not (checks["chunk_ids_unique"] and checks["nan"] == 0 and checks["norm_ok"] and checks["dim"] == DIM):
        raise SystemExit(f"Verificación fallida: {checks}")

    out = pa.Table.from_arrays(
        [
            table["chunk_id"],
            table["document_id"],
            table["source"],
            table["lang"],
            pc.cast(table["token_count"], pa.int32()),
            pa.FixedSizeListArray.from_arrays(pa.array(vectors.reshape(-1), pa.float32()), DIM),
        ],
        schema=OUTPUT_SCHEMA,
    )
    pq.write_table(out, output, compression="zstd")

    n = len(chunk_ids)
    per_chunk = elapsed / n
    print(json.dumps({
        "model": MODEL,
        "hidden_size": hidden,
        "device": "cpu",
        "torch_threads": torch.get_num_threads(),
        "batch_size": args.batch_size,
        "documents": n_docs,
        "chunks": n,
        "seconds_total": round(elapsed, 2),
        "ms_per_chunk": round(per_chunk * 1000, 2),
        "chunks_per_second": round(n / elapsed, 1),
        "peak_rss_mb_during_encode": round(rss.peak / 2**20, 1),
        "ru_maxrss_mb_process": round(ru_maxrss_bytes() / 2**20, 1),
        "estimate_full_corpus_hours": round(per_chunk * FULL_CORPUS_CHUNKS / 3600, 2),
        "checks": checks,
        "output": str(output),
        "output_bytes": output.stat().st_size,
    }, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
