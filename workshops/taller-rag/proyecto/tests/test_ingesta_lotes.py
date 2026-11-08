"""Ingesta por lotes: mismo resultado que una carga de una sola vez e idempotencia.

Usa Parquet sintéticos de 50 filas (no datos reales) y un cliente Milvus falso.
"""
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from app import milvus_schema as ms
from scripts import ingest_milvus as ing

N = 50


class FakeMilvus:
    """Cliente en memoria con semántica de upsert por clave primaria."""

    def __init__(self):
        self.rows = {}
        self.created = False

    def has_collection(self, name):
        return self.created

    def describe_collection(self, name):
        return {"fields": [{"name": n} for n in ms.FIELD_NAMES]}

    def create_collection(self, collection_name, schema, index_params):
        self.created = True

    def upsert(self, collection_name, data):
        for row in data:
            self.rows[row["chunk_id"]] = row

    def query(self, collection_name, ids=None, filter="", output_fields=None, consistency_level=None):
        if output_fields == ["count(*)"]:
            return [{"count(*)": len(self.rows)}]
        return [{"chunk_id": i} for i in ids if i in self.rows]


def escribir_parquets(tmp_path):
    rng = np.random.default_rng(42)
    vectors = rng.normal(size=(N, ms.DIM)).astype(np.float32)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    ids = [f"{i:064x}" for i in range(N)]
    emb = pa.table({
        "chunk_id": ids,
        "document_id": [f"doc-{i // 3}" for i in range(N)],
        "source": ["media_cloud" if i % 2 else "bluesky" for i in range(N)],
        "lang": ["es" if i % 3 else "en" for i in range(N)],
        "token_count": pa.array([10 + i for i in range(N)], pa.int32()),
        "vector": pa.FixedSizeListArray.from_arrays(pa.array(vectors.reshape(-1), pa.float32()), ms.DIM),
    })
    # El Parquet de chunks va en otro orden para comprobar que la unión es por chunk_id.
    order = list(reversed(range(N)))
    chunks = pa.table({
        "chunk_id": [ids[i] for i in order],
        "document_id": [f"doc-{i // 3}" for i in order],
        "source": ["media_cloud" if i % 2 else "bluesky" for i in order],
        "url": [None if i % 7 == 0 else f"https://ejemplo.invalid/{i}" for i in order],
        "created_at_utc": [None if i % 5 == 0 else "2026-01-01T00:00:00+00:00" for i in order],
        "token_count": pa.array([10 + i for i in order], pa.int32()),
        "text": [f"texto sintético {i}" for i in order],
    })
    emb_path, chunks_path = tmp_path / "emb.parquet", tmp_path / "chunks.parquet"
    pq.write_table(emb, emb_path, row_group_size=7)
    pq.write_table(chunks, chunks_path, row_group_size=11)
    return emb_path, chunks_path


def cargar(emb_path, chunks_path, read_batch, client=None):
    client = client or FakeMilvus()
    ms.ensure_collection(client, "c")
    records, expected = ing.records_from_embeddings(emb_path, chunks_path, read_batch=read_batch)
    sent = ing.upsert_all(client, "c", records, batch_size=8)
    return client, sent, expected


def test_lotes_de_20_igual_a_una_sola_vez(tmp_path):
    emb_path, chunks_path = escribir_parquets(tmp_path)
    por_lotes, sent_lotes, expected = cargar(emb_path, chunks_path, read_batch=20)
    una_vez, sent_una, _ = cargar(emb_path, chunks_path, read_batch=10_000)
    assert expected == N and len(sent_lotes) == N
    assert sent_lotes == sent_una  # mismo orden de envío
    assert por_lotes.rows.keys() == una_vez.rows.keys()
    for cid, row in por_lotes.rows.items():
        other = una_vez.rows[cid]
        assert {k: v for k, v in row.items() if k != "vector"} == {k: v for k, v in other.items() if k != "vector"}
        assert np.array_equal(np.asarray(row["vector"], np.float32), np.asarray(other["vector"], np.float32))
        assert sorted(row) == sorted(ms.FIELD_NAMES)


def test_vectores_y_metadatos_se_unen_por_chunk_id(tmp_path):
    emb_path, chunks_path = escribir_parquets(tmp_path)
    client, _, _ = cargar(emb_path, chunks_path, read_batch=20)
    emb = pq.read_table(emb_path).to_pylist()
    for original in emb:
        row = client.rows[original["chunk_id"]]
        i = int(original["chunk_id"], 16)
        assert row["text"] == f"texto sintético {i}" and row["lang"] == original["lang"]
        assert np.allclose(row["vector"], original["vector"])
    assert client.rows[f"{0:064x}"]["url"] == "" and client.rows[f"{0:064x}"]["created_at_utc"] == ""


def test_segunda_carga_no_duplica(tmp_path):
    emb_path, chunks_path = escribir_parquets(tmp_path)
    client, sent, _ = cargar(emb_path, chunks_path, read_batch=20)
    cargar(emb_path, chunks_path, read_batch=20, client=client)
    assert ing.count_total(client, "c", wait=0) == N
    assert ing.count_present(client, "c", sent, batch_size=15, wait=0) == N
