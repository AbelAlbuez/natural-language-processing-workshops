"""Pruebas de contrato sin servicios: no se conectan a Milvus ni a Ollama."""
import hashlib

import pytest
from pymilvus import DataType

from app import milvus_schema as ms
from app import rag
from scripts import chunk_corpus
from scripts import ingest_milvus as ing


# ── Dobles de prueba ─────────────────────────────────────────────────────────
class FakeMilvus:
    """Cliente mínimo en memoria con semántica de upsert por clave primaria."""

    def __init__(self, existing_fields=None):
        self.collections = {}
        self.created = 0
        if existing_fields is not None:
            self.collections["c"] = {"fields": existing_fields, "rows": {}}

    def has_collection(self, name):
        return name in self.collections

    def describe_collection(self, name):
        return {"fields": [{"name": n} for n in self.collections[name]["fields"]]}

    def create_collection(self, collection_name, schema, index_params):
        self.created += 1
        self.collections[collection_name] = {"fields": [f.name for f in schema.fields], "rows": {}}

    def upsert(self, collection_name, data):
        for row in data:
            self.collections[collection_name]["rows"][row["chunk_id"]] = row

    def query(self, collection_name, ids=None, filter="", output_fields=None, consistency_level=None):
        rows = self.collections[collection_name]["rows"]
        if output_fields == ["count(*)"]:
            return [{"count(*)": len(rows)}]
        return [{"chunk_id": i} for i in ids if i in rows]


def settings(**overrides):
    base = dict(milvus_uri="http://x", ollama_url="http://y", default_model="m",
                available_models=("m",), score_threshold=0.8, max_context_tokens=100,
                run_log="")
    base.update(overrides)
    return rag.Settings(**base)


def frag(n, score, tokens=40):
    return {"chunk_id": f"c{n}", "document_id": f"d{n}", "source": "media_cloud",
            "url": f"https://e/{n}", "text": f"texto {n}", "token_count": tokens, "score": score}


def chunk_row(cid="a" * 64, text="hola"):
    return {"chunk_id": cid, "document_id": "doc", "source": "bluesky", "url": None,
            "created_at_utc": None, "token_count": 3, "text": text}


# ── Identificadores de chunk ─────────────────────────────────────────────────
def test_chunk_ids_are_stable_and_follow_documented_formula():
    row = {"document_id": "doc-1", "text": "x" * 600, "url": None, "source": "gdelt", "created_at_utc": None}
    offsets = [(i * 2, i * 2 + 2) for i in range(300)]  # 300 tokens -> 2 chunks (256/48)
    first = list(chunk_corpus.chunk_records(row, offsets))
    second = list(chunk_corpus.chunk_records(row, offsets))
    assert [c["chunk_id"] for c in first] == [c["chunk_id"] for c in second]
    assert len(first) == 2 and first[1]["token_start"] == 208
    for c in first:
        payload = f"doc-1\x1f{c['chunk_index']}\x1f{chunk_corpus.STRATEGY}".encode()
        assert c["chunk_id"] == hashlib.sha256(payload).hexdigest()
    assert len({c["chunk_id"] for c in first}) == 2


def test_ingest_record_keeps_chunk_id_and_normalizes_nulls():
    rec = ing.to_record(chunk_row(), [0.0] * ms.DIM, "es")
    assert rec["chunk_id"] == "a" * 64
    assert rec["url"] == "" and rec["created_at_utc"] == ""
    assert sorted(rec) == sorted(ms.FIELD_NAMES)


def test_ingest_rejects_wrong_dimension_and_oversized_text():
    with pytest.raises(ValueError):
        ing.to_record(chunk_row(), [0.0] * 10, "es")
    with pytest.raises(ValueError):
        ing.to_record(chunk_row(text="é" * 9000), [0.0] * ms.DIM, "es")  # 18.000 bytes


def test_upsert_is_idempotent():
    client = FakeMilvus()
    ms.ensure_collection(client, "c")
    records = [ing.to_record(chunk_row(cid=f"{i:064d}"), [0.0] * ms.DIM, "en") for i in range(10)]
    for _ in range(2):
        ing.upsert_all(client, "c", records, batch_size=3)
    ids = [r["chunk_id"] for r in records]
    assert ing.count_total(client, "c") == 10
    assert ing.count_present(client, "c", ids, batch_size=4) == 10


# ── Esquema de la colección (sin conexión) ───────────────────────────────────
def test_schema_fields_types_and_primary_key():
    schema = ms.build_schema()
    fields = {f.name: f for f in schema.fields}
    assert list(fields) == ms.FIELD_NAMES
    assert set(fields) == {"chunk_id", "vector", "document_id", "source", "lang", "url",
                           "created_at_utc", "token_count", "text"}
    assert fields["chunk_id"].is_primary and fields["chunk_id"].dtype == DataType.VARCHAR
    assert fields["vector"].dtype == DataType.FLOAT_VECTOR and fields["vector"].params["dim"] == 384
    assert fields["token_count"].dtype == DataType.INT32
    assert fields["text"].params["max_length"] >= 6800  # mayor texto medido en bytes
    assert ms.COLLECTION_NAME == "rag_e5s_tok256_v1"


def test_index_uses_inner_product_and_declared_params():
    (index,) = list(ms.build_index_params())
    assert index.field_name == "vector" and index.index_type == ms.INDEX_TYPE == "HNSW"
    assert index._configs["metric_type"] == "IP"
    assert {k: index._configs[k] for k in ms.INDEX_PARAMS} == ms.INDEX_PARAMS
    assert ms.SEARCH_PARAMS["metric_type"] == "IP" and ms.SEARCH_PARAMS["params"]["ef"] >= 15


def test_ensure_collection_creates_once_and_rejects_foreign_schema():
    client = FakeMilvus()
    assert ms.ensure_collection(client, "c") is True
    assert ms.ensure_collection(client, "c") is False
    assert client.created == 1
    legacy = FakeMilvus(existing_fields=["chunk_id", "vector", "text", "title", "position"])
    with pytest.raises(ms.SchemaMismatch):
        ms.ensure_collection(legacy, "c")


# ── Plantilla de prompt ──────────────────────────────────────────────────────
def test_prompt_template_is_versioned_and_numbers_fragments():
    assert rag.PROMPT_NAME == "prompt_v1" and rag.PROMPT_VERSION
    assert "{context}" in rag.PROMPT_TEMPLATE and "{question}" in rag.PROMPT_TEMPLATE
    assert rag.PROMPT_SHA256 == hashlib.sha256(rag.PROMPT_TEMPLATE.encode()).hexdigest()
    selected, _ = rag.build_context([frag(1, 0.9), frag(2, 0.85)], 1000)
    prompt = rag.render_prompt("¿Qué pasó?", selected)
    assert "[1] fuente=media_cloud documento=d1" in prompt
    assert "[2] fuente=media_cloud documento=d2" in prompt
    assert prompt.rstrip().endswith("RESPUESTA (con citas [n]):")
    assert "¿Qué pasó?" in prompt and "citar" in prompt


def test_extract_citations_maps_refs_and_flags_invalid():
    selected, _ = rag.build_context([frag(1, 0.9), frag(2, 0.85)], 1000)
    valid, invalid = rag.extract_citations("Dato A [2]. Dato B [1][2]. Dato C [7].", selected)
    assert [c["ref"] for c in valid] == [2, 1]
    assert valid[0]["chunk_id"] == "c2"
    assert invalid == [7]


# ── Abstención ───────────────────────────────────────────────────────────────
def test_should_abstain_threshold():
    assert rag.should_abstain([], 0.5)
    assert rag.should_abstain([frag(1, 0.79)], 0.8)
    assert not rag.should_abstain([frag(1, 0.80)], 0.8)


def test_abstention_does_not_call_llm():
    def boom(*_):
        raise AssertionError("no debe llamarse al LLM")

    out = rag.answer("pregunta", settings(), retriever=lambda q, k: [frag(1, 0.5)], generator=boom)
    assert out["abstained"] and out["abstention_reason"] == "score_below_threshold"
    assert out["answer"] == rag.ABSTENTION_MESSAGE
    assert out["params"]["timings"]["generation_s"] == 0.0


def test_answer_calls_llm_and_records_params(tmp_path):
    log = tmp_path / "runs.jsonl"
    calls = []

    def fake_llm(prompt, model):
        calls.append(model)
        return "Respuesta [1].", {"prompt_tokens": 10, "completion_tokens": 3}

    out = rag.answer("pregunta", settings(run_log=str(log)), k=2,
                     retriever=lambda q, k: [frag(1, 0.9), frag(2, 0.85)], generator=fake_llm)
    assert calls == ["m"] and not out["abstained"]
    assert [c["chunk_id"] for c in out["citations"]] == ["c1"]
    p = out["params"]
    assert (p["model"], p["top_k"], p["score_threshold"], p["prompt_name"]) == ("m", 2, 0.8, "prompt_v1")
    assert set(p["timings"]) == {"retrieval_s", "generation_s", "total_s"}
    logged = log.read_text(encoding="utf-8")
    assert "prompt_v1" in logged and "texto 1" not in logged  # sin texto de documentos


# ── Presupuesto de contexto ──────────────────────────────────────────────────
def test_budget_keeps_whole_fragments_only():
    fragments = [frag(1, 0.9, 40), frag(2, 0.88, 40), frag(3, 0.87, 40)]
    selected, dropped = rag.build_context(fragments, max_tokens=100)
    assert [f["ref"] for f in selected] == [1, 2] and dropped == 1
    assert [f["text"] for f in selected] == ["texto 1", "texto 2"]  # sin recortar
    assert sum(f["token_count"] for f in selected) <= 100


def test_budget_too_small_for_first_fragment_abstains():
    out = rag.answer("pregunta", settings(max_context_tokens=10),
                     retriever=lambda q, k: [frag(1, 0.95, 40)],
                     generator=lambda *_: pytest.fail("no debe llamarse al LLM"))
    assert out["abstained"] and out["abstention_reason"] == "context_budget"


# ── Configuración ────────────────────────────────────────────────────────────
def test_settings_require_model_and_urls(monkeypatch):
    for name in ("LLM_MODEL", "MILVUS_URI", "OLLAMA_URL", "LLM_MODELS"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(rag.ConfigError):
        rag.Settings.from_env()
    monkeypatch.setenv("LLM_MODEL", "a")
    monkeypatch.setenv("LLM_MODELS", "b, c")
    monkeypatch.setenv("MILVUS_URI", "http://milvus:19530")
    monkeypatch.setenv("OLLAMA_URL", "http://ollama:11434/")
    s = rag.Settings.from_env()
    assert s.available_models == ("a", "b", "c") and s.ollama_url == "http://ollama:11434"
