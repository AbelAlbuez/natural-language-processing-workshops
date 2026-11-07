"""Experimento principal: partición de prueba, varios modelos, una repetición.

Qué hace: con la API levantada, llama primero a POST /retrieve para cada pregunta de
prueba (la recuperación no depende del modelo) y después a POST /ask con cada modelo y
cada pregunta, en ese orden (un modelo tras otro, para no forzar a Ollama a cambiar de
modelo). La configuración (temperatura, repeat_penalty, umbral, k) es la de la API; el
script solo la registra. Una corrida con error se registra como fallo y no se reintenta.
Se detiene si supera --limite-s segundos.

Lee:      docs/gold_standard.csv (solo filas con split=prueba) y la API (--api).
Escribe:  data/experimento_prueba.jsonl con registros "retrieve" (document_id y scores) y
          "ask" (código HTTP, abstención, citas, document_id citados, tiempos y parámetros).
          Nunca guarda texto de preguntas, fragmentos ni respuestas. La API, además, añade
          cada corrida exitosa a su propio registro (RAG_RUN_LOG).

Uso (con la API levantada; en el equipo de referencia tardó unos 34 minutos):
    python -m scripts.ejecutar_experimento --api http://localhost:8000
Las métricas se calculan después con scripts/analisis_resultados.py.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import time
from pathlib import Path

SPLIT = "prueba"
MODELOS = ["gemma2:2b", "qwen2.5:1.5b", "llama3.2:1b", "llama3.2:3b"]


def leer_preguntas(gold_path):
    with open(gold_path, encoding="utf-8", newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if r["split"] == SPLIT]
    if not rows:
        raise SystemExit(f"{gold_path} no tiene filas con split={SPLIT}.")
    return rows


def registro_ask(model, r, resp_status, body):
    """Convierte la respuesta de /ask en un registro sin texto."""
    rec = {"fase": "ask", "modelo": model, "id": r["id"], "tipo": r["tipo"], "evidencia": r["evidencia_doc_id"],
           "http": resp_status}
    if resp_status == 200:
        ev = {f["ref"]: f for f in body["evidence"]}
        rec.update(
            abstained=body["abstained"], reason=body["abstention_reason"],
            citas_validas=[c["ref"] for c in body["citations"]], citas_invalidas=body["invalid_citations"],
            docs_citados=[ev[c["ref"]]["document_id"] for c in body["citations"]],
            evidencia_citada=bool(r["evidencia_doc_id"]) and any(
                ev[c["ref"]]["document_id"] == r["evidencia_doc_id"] for c in body["citations"]),
            respuesta_chars=len(body["answer"]), timings=body["params"]["timings"], usage=body["usage"],
            repeat_penalty=body["params"].get("repeat_penalty"), threshold=body["params"]["score_threshold"],
        )
    else:
        d = body.get("detail", {}) if isinstance(body, dict) else {}
        items = d.items() if isinstance(d, dict) else [("detail", d)]
        rec["error"] = {k: str(v)[:160] for k, v in items}
    return rec


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--gold", default="docs/gold_standard.csv")
    parser.add_argument("--api", default=os.getenv("RAG_API_URL", "http://localhost:8000"))
    parser.add_argument("--modelos", nargs="+", default=MODELOS)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--salida", default="data/experimento_prueba.jsonl")
    parser.add_argument("--limite-s", type=float, default=7200, help="Tiempo máximo en segundos (por defecto, 2 horas).")
    parser.add_argument("--anexar", action="store_true", help="Permite añadir a un archivo de salida existente.")
    args = parser.parse_args(argv)

    import requests

    api = args.api.rstrip("/")
    salida = Path(args.salida)
    if salida.exists() and not args.anexar:
        raise SystemExit(f"{salida} ya existe; use --anexar o elija otra --salida.")
    salida.parent.mkdir(parents=True, exist_ok=True)
    rows = leer_preguntas(args.gold)
    t_start = time.perf_counter()

    with salida.open("a", encoding="utf-8") as out:
        def log(rec):
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            out.flush()

        for r in rows:  # recuperación: igual para todos los modelos
            resp = requests.post(f"{api}/retrieve", json={"question": r["pregunta"], "k": args.k}, timeout=120)
            frags = resp.json().get("fragments", []) if resp.ok else []
            log({"fase": "retrieve", "id": r["id"], "tipo": r["tipo"], "fuente": r["fuente_esperada"],
                 "idioma": r["idioma"], "http": resp.status_code, "evidencia": r["evidencia_doc_id"],
                 "docs": [f["document_id"] for f in frags], "scores": [f["score"] for f in frags]})
        print("retrieve listo", flush=True)

        for model in args.modelos:
            for r in rows:
                if time.perf_counter() - t_start > args.limite_s:
                    log({"fase": "detenido", "motivo": f"más de {args.limite_s:.0f} s"})
                    print("DETENIDO por tiempo", flush=True)
                    return 0
                t0 = time.perf_counter()
                try:
                    resp = requests.post(f"{api}/ask", json={"question": r["pregunta"], "model": model, "k": args.k},
                                         timeout=330)
                    try:
                        body = resp.json()
                    except ValueError:
                        body = {}
                    rec = registro_ask(model, r, resp.status_code, body)
                except requests.RequestException as exc:
                    rec = {"fase": "ask", "modelo": model, "id": r["id"], "tipo": r["tipo"],
                           "evidencia": r["evidencia_doc_id"], "http": None, "error": {"excepcion": type(exc).__name__}}
                rec["segundos"] = round(time.perf_counter() - t0, 2)
                log(rec)
                print(f"{model} {r['id']} http={rec.get('http')} {rec['segundos']}s", flush=True)
    print(f"FIN en {round(time.perf_counter() - t_start)} s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
