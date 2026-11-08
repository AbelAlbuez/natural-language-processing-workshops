"""Prueba de humo de la API: imprime una tabla y guarda el detalle en data/smoke_api.jsonl.

Uso: python -m scripts.smoke_api [--api http://localhost:8000]
El JSONL solo guarda códigos, tiempos y conteos; nunca texto de documentos ni respuestas.
Sale con código 1 si alguna comprobación falla (SKIP no cuenta como fallo).
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

GENERIC_QUERY = "elecciones presidenciales en Colombia"
NONSENSE_QUERY = "qzxv blorf kwyjibo trznn plimp"


def call(method, url, **kwargs):
    start = time.perf_counter()
    try:
        r = requests.request(method, url, **kwargs)
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        return r.status_code, round(time.perf_counter() - start, 3), body
    except requests.RequestException as exc:
        return None, round(time.perf_counter() - start, 3), {"error": type(exc).__name__}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--out", default="data/smoke_api.jsonl")
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()
    api = args.api.rstrip("/")
    rows = []

    def record(name, status, seconds, result, **info):
        rows.append({"endpoint": name, "status": status, "seconds": seconds, "result": result, **info})

    status, sec, body = call("GET", f"{api}/health", timeout=10)
    record("GET /health", status, sec, "OK" if status == 200 and body.get("status") == "ok" else "FAIL")

    status, sec, body = call("GET", f"{api}/health", params={"deep": "true"}, timeout=30)
    milvus, ollama = body.get("milvus", {}), body.get("ollama", {})
    models = ollama.get("models") or []
    record("GET /health?deep", status, sec, "OK" if status == 200 and milvus.get("ok") else "FAIL",
           milvus_rows=milvus.get("rows"), ollama_ok=ollama.get("ok"), models=len(models),
           missing=ollama.get("missing"))

    status, sec, body = call("POST", f"{api}/retrieve", json={"question": GENERIC_QUERY, "k": args.k}, timeout=60)
    frags = body.get("fragments", [])
    scores = [f.get("score") for f in frags]
    ok = status == 200 and 0 < len(frags) <= args.k and scores == sorted(scores, reverse=True)
    record("POST /retrieve", status, sec, "OK" if ok else "FAIL", fragments=len(frags),
           top_score=scores[0] if scores else None)

    if models:
        status, sec, body = call("POST", f"{api}/ask",
                                 json={"question": GENERIC_QUERY, "model": models[0], "k": args.k}, timeout=300)
        ok = status == 200 and (body.get("abstained") or bool(body.get("citations")))
        record("POST /ask", status, sec, "OK" if ok else "FAIL", model=models[0],
               abstained=body.get("abstained"), citations=len(body.get("citations", [])),
               invalid_citations=len(body.get("invalid_citations", [])),
               timings=(body.get("params") or {}).get("timings"))
    else:
        record("POST /ask", None, 0.0, "SKIP", note="Ollama sin modelos descargados")

    status, sec, body = call("POST", f"{api}/ask", json={"question": NONSENSE_QUERY, "k": args.k}, timeout=120)
    ok = status == 200 and body.get("abstained") is True
    evidence = body.get("evidence") or []
    record("POST /ask (sin evidencia)", status, sec, "OK" if ok else "FAIL",
           abstained=body.get("abstained"), reason=body.get("abstention_reason"),
           top_score=evidence[0]["score"] if evidence else None)

    status, sec, body = call("POST", f"{api}/ask", json={"question": GENERIC_QUERY, "model": "no-permitido:0b"}, timeout=30)
    record("POST /ask (modelo no permitido)", status, sec, "OK" if status == 400 else "FAIL")

    stamp = datetime.now(timezone.utc).isoformat()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps({"timestamp_utc": stamp, "api": api, **row}, ensure_ascii=False) + "\n")

    width = max(len(r["endpoint"]) for r in rows)
    print(f"{'Endpoint'.ljust(width)}  HTTP  Tiempo(s)  Resultado")
    for r in rows:
        print(f"{r['endpoint'].ljust(width)}  {str(r['status'] or '-'):>4}  {r['seconds']:>9.3f}  {r['result']}")
    print(f"Detalle: {out}")
    raise SystemExit(1 if any(r["result"] == "FAIL" for r in rows) else 0)


if __name__ == "__main__":
    main()
