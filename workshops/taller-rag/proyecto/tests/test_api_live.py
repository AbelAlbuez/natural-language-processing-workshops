"""Pruebas en vivo contra la API (localhost). Solo corren con RAG_LIVE=1.

    RAG_LIVE=1 pytest tests/test_api_live.py

Requieren Milvus con la colección cargada y la API levantada (docker compose up -d api).
Las pruebas de /ask se omiten si Ollama no tiene modelos descargados. La prueba de
Milvus caído no usa la API en vivo: ejecuta la app en el proceso con un host inválido.
No imprimen texto de documentos.
"""
import csv
import os
import re
from pathlib import Path

import pytest
import requests

pytestmark = pytest.mark.skipif(os.getenv("RAG_LIVE") != "1", reason="Defina RAG_LIVE=1 para pruebas en vivo.")

API = os.getenv("RAG_API_URL", "http://localhost:8000").rstrip("/")
GOLD = Path(__file__).resolve().parents[1] / "docs" / "gold_standard_plantilla.csv"
DEV_IDS = ["G01", "G02", "G04", "G09", "G10", "G12", "G14", "G16", "G17", "G18",
           "G20", "G21", "G25", "G27", "G30", "G31", "G32", "G33", "G36", "G39"]
GENERIC_QUERY = "elecciones presidenciales en Colombia"
NONSENSE_QUERY = "qzxv blorf kwyjibo trznn plimp"
K = 5


@pytest.fixture(scope="module")
def health():
    r = requests.get(f"{API}/health", params={"deep": "true"}, timeout=30)
    assert r.status_code == 200
    return r.json()


@pytest.fixture(scope="module")
def model(health):
    pulled = health.get("ollama", {}).get("models") or []
    if not pulled:
        pytest.skip("Ollama no tiene modelos descargados: /ask queda pendiente.")
    return pulled[0]


def dev_questions(n=3):
    rows = list(csv.DictReader(GOLD.open(encoding="utf-8")))
    filled = [r for r in rows if r["id_pregunta"] in DEV_IDS and r["pregunta"].strip()]
    return [(r["id_pregunta"], r["pregunta"].strip()) for r in filled[:n]]


def assert_fragments(fragments, k):
    assert 0 < len(fragments) <= k
    for f in fragments:
        assert isinstance(f["score"], float)
        assert f["document_id"] and f["source"] in {"bluesky", "media_cloud", "gdelt"}
        assert "url" in f
    scores = [f["score"] for f in fragments]
    assert scores == sorted(scores, reverse=True)


# ── /health ──────────────────────────────────────────────────────────────────
def test_health_shallow():
    r = requests.get(f"{API}/health", timeout=10)
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_health_deep_reports_milvus_and_ollama(health):
    assert {"milvus", "ollama"} <= set(health)
    assert health["milvus"]["ok"] and health["milvus"]["rows"] > 0
    assert "ok" in health["ollama"]


# ── /retrieve ────────────────────────────────────────────────────────────────
def test_retrieve_contract_generic_query():
    r = requests.post(f"{API}/retrieve", json={"question": GENERIC_QUERY, "k": K}, timeout=60)
    assert r.status_code == 200
    assert_fragments(r.json()["fragments"], K)


@pytest.mark.parametrize("position", [0, 1, 2])
def test_retrieve_dev_questions(position):
    questions = dev_questions()
    if len(questions) <= position:
        pytest.skip("El gold standard aún no tiene texto en las preguntas de desarrollo.")
    _, question = questions[position]
    r = requests.post(f"{API}/retrieve", json={"question": question, "k": K}, timeout=60)
    assert r.status_code == 200
    assert_fragments(r.json()["fragments"], K)


# ── /ask ─────────────────────────────────────────────────────────────────────
def test_ask_citations_point_to_returned_fragments(model):
    r = requests.post(f"{API}/ask", json={"question": GENERIC_QUERY, "model": model, "k": K}, timeout=300)
    assert r.status_code == 200, r.text[:300]
    out = r.json()
    if out["abstained"]:
        pytest.skip(f"La pregunta genérica produjo abstención ({out['abstention_reason']}).")
    refs = {f["ref"]: f["chunk_id"] for f in out["evidence"]}
    cited = {int(n) for n in re.findall(r"\[(\d+)\]", out["answer"])}
    assert out["citations"], "La respuesta no cita ningún fragmento."
    for c in out["citations"]:
        assert refs[c["ref"]] == c["chunk_id"]
    assert cited - set(refs) == set(out["invalid_citations"])
    assert out["params"]["prompt_name"] == "prompt_v1"


@pytest.mark.xfail(
    strict=False,
    reason="Pendiente de calibración del umbral RAG_SCORE_THRESHOLD con preguntas de desarrollo; "
           "con E5 las puntuaciones se concentran entre 0,84 y 0,87",
)
def test_ask_nonsense_abstains_without_llm():
    r = requests.post(f"{API}/ask", json={"question": NONSENSE_QUERY, "k": K}, timeout=120)
    assert r.status_code == 200
    out = r.json()
    assert out["abstained"], f"Sin abstención: mejor score {out['evidence'][0]['score'] if out['evidence'] else None}"
    assert out["params"]["timings"]["generation_s"] == 0.0
    assert out["usage"] == {}


def test_ask_disallowed_model_returns_400():
    r = requests.post(f"{API}/ask", json={"question": GENERIC_QUERY, "model": "modelo-no-permitido:0b"}, timeout=30)
    assert r.status_code == 400


# ── Milvus caído (en proceso, host inválido) ─────────────────────────────────
def test_milvus_down_returns_503(monkeypatch):
    from fastapi import HTTPException

    import app.api as api

    monkeypatch.setenv("MILVUS_URI", "http://127.0.0.1:1")
    monkeypatch.setenv("OLLAMA_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("LLM_MODEL", "modelo-prueba")
    monkeypatch.setenv("RAG_RUN_LOG", "")
    api.settings.cache_clear()
    try:
        with pytest.raises(HTTPException) as exc:
            api.retrieve(api.RetrieveRequest(question=GENERIC_QUERY, k=3))
        assert exc.value.status_code == 503
        assert exc.value.detail["servicio"] == "milvus"
    finally:
        api.settings.cache_clear()
