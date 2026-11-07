"""Calibración del umbral de abstención SOLO con la partición de desarrollo.

Qué hace: para cada pregunta de desarrollo del gold standard llama a POST /retrieve
(k fragmentos) y guarda el score máximo. Con esos scores busca un umbral t que cumpla dos
criterios a la vez: abstenerse en todas las no respondibles (score máximo < t) y
responder al menos una fracción mínima de las respondibles (score máximo >= t). También
evalúa umbrales fijos solo como información.

Lee:      docs/gold_standard.csv (solo filas con split=desarrollo) y la API (--api).
Escribe:  data/calibracion_dev.json (IDs, tipo, fuente, idioma, score máximo y conteos;
          nunca texto de preguntas ni de fragmentos).

Uso (con la API levantada):
    python -m scripts.calibrar_umbral --api http://localhost:8000

No modifica RAG_SCORE_THRESHOLD: solo propone. La partición de prueba no se usa.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
from pathlib import Path

SPLIT = "desarrollo"


def evaluar_umbral(scores_resp, scores_nr, t):
    """Conteos de un umbral: respondibles respondidas (>= t) y no respondibles abstenidas (< t)."""
    return {
        "umbral": t,
        "respondibles_respondidas": sum(1 for s in scores_resp if s >= t),
        "respondibles": len(scores_resp),
        "no_respondibles_abstenidas": sum(1 for s in scores_nr if s < t),
        "no_respondibles": len(scores_nr),
    }


def proponer_umbral(scores_resp, scores_nr, min_respondidas=0.9, paso=0.001):
    """Busca un umbral que abstenga en todas las no respondibles y responda al menos
    `min_respondidas` de las respondibles.

    - umbral_min_abstencion: el menor múltiplo de `paso` estrictamente mayor que el score
      máximo de las no respondibles (abstiene en todas).
    - umbral_max_respuesta: el mayor umbral que aún responde las necesarias (el score de la
      respondible número `necesarias` en orden descendente).
    Es factible si umbral_min_abstencion <= umbral_max_respuesta; la propuesta es entonces
    umbral_min_abstencion (el menos restrictivo). Si no, propuesta = None.
    """
    if not scores_resp or not scores_nr:
        raise ValueError("Se necesitan respondibles y no respondibles para calibrar.")
    necesarias = math.ceil(min_respondidas * len(scores_resp))
    max_nr = max(scores_nr)
    escala = round(1 / paso)
    t_min = round(math.floor(round(max_nr * escala, 6)) / escala + paso, 6)
    if t_min <= max_nr:
        t_min = round(t_min + paso, 6)
    t_max = sorted(scores_resp, reverse=True)[necesarias - 1]
    factible = t_min <= t_max
    return {
        "min_respondidas": min_respondidas,
        "necesarias": necesarias,
        "max_score_no_respondibles": max_nr,
        "umbral_min_abstencion": t_min,
        "umbral_max_respuesta": t_max,
        "factible": factible,
        "propuesta": t_min if factible else None,
        "con_umbral_min_abstencion": evaluar_umbral(scores_resp, scores_nr, t_min),
        "con_umbral_max_respuesta": evaluar_umbral(scores_resp, scores_nr, t_max),
    }


def leer_preguntas(gold_path):
    with open(gold_path, encoding="utf-8", newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if r["split"] == SPLIT]
    if not rows:
        raise SystemExit(f"{gold_path} no tiene filas con split={SPLIT}.")
    return rows


def puntuar(rows, api, k):
    import requests

    out = []
    for r in rows:
        resp = requests.post(f"{api}/retrieve", json={"question": r["pregunta"], "k": k}, timeout=120)
        resp.raise_for_status()
        frags = resp.json()["fragments"]
        docs = [f["document_id"] for f in frags]
        out.append({"id": r["id"], "tipo": r["tipo"], "fuente": r["fuente_esperada"], "idioma": r["idioma"],
                    "score_max": max(f["score"] for f in frags),
                    "evidencia_en_topk": (r["evidencia_doc_id"] in docs) if r["evidencia_doc_id"] else None})
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--gold", default="docs/gold_standard.csv")
    parser.add_argument("--api", default=os.getenv("RAG_API_URL", "http://localhost:8000"))
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--min-respondidas", type=float, default=0.9)
    parser.add_argument("--evaluar", type=float, nargs="*", default=[0.80, 0.8465, 0.876],
                        help="Umbrales fijos que se evalúan solo como información.")
    parser.add_argument("--salida", default="data/calibracion_dev.json")
    args = parser.parse_args(argv)

    preguntas = puntuar(leer_preguntas(args.gold), args.api.rstrip("/"), args.k)
    resp = [p["score_max"] for p in preguntas if p["tipo"] != "no_respondible"]
    nr = [p["score_max"] for p in preguntas if p["tipo"] == "no_respondible"]
    resultado = {
        "particion": SPLIT, "k": args.k,
        "preguntas": preguntas,
        "propuesta": proponer_umbral(resp, nr, args.min_respondidas),
        "umbrales_evaluados": [evaluar_umbral(resp, nr, t) for t in args.evaluar],
    }
    Path(args.salida).parent.mkdir(parents=True, exist_ok=True)
    Path(args.salida).write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")

    p = resultado["propuesta"]
    print(f"desarrollo: {len(resp)} respondibles (necesarias {p['necesarias']}), {len(nr)} no respondibles")
    print(f"máximo score no respondibles: {p['max_score_no_respondibles']:.4f} | "
          f"umbral mínimo de abstención: {p['umbral_min_abstencion']:.3f} | "
          f"umbral máximo de respuesta: {p['umbral_max_respuesta']:.4f}")
    print("propuesta:", f"{p['propuesta']:.3f}" if p["factible"] else "ningún umbral cumple ambos criterios")
    for u in resultado["umbrales_evaluados"]:
        print(f"  t={u['umbral']:.4f}: respondidas {u['respondibles_respondidas']}/{u['respondibles']} | "
              f"no respondibles abstenidas {u['no_respondibles_abstenidas']}/{u['no_respondibles']}")
    print(f"Detalle: {args.salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
