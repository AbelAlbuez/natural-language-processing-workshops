"""Métricas del experimento sobre la partición de prueba, con scripts/metricas_rag.py.

Uso:
    python -m scripts.analisis_resultados \
        --runs data/experimento_prueba.jsonl --gold docs/gold_standard.csv \
        --salida data/resultados_prueba.json

Entradas:
- runs: JSONL con registros "retrieve" (por pregunta: document_id recuperados en orden y
  sus scores) y "ask" (por modelo y pregunta: código HTTP, abstención, citas válidas e
  inválidas, document_id citados, segundos y parámetros).
- gold: CSV del gold standard; se usan solo las filas con split=prueba.

Reglas:
- Una corrida con error cuenta como fallo y permanece en el denominador.
- El umbral del sistema es fijo (0,80) para todos los modelos; no se recalcula nada: la
  abstención es la que registró la API.
- La recuperación se mide a nivel de documento (evidencia_doc_id como único relevante) y
  no depende del modelo.
- El análisis de umbrales alternativos es solo informativo y usa el score máximo
  registrado en la fase retrieve.

Solo escribe conteos y métricas; nunca texto de preguntas ni de respuestas.
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import OrderedDict
from pathlib import Path

from scripts.metricas_rag import (
    abstention_precision_recall,
    mean_defined,
    ndcg_at_k,
    recall_at_k,
    reciprocal_rank,
    retrieval_summary,
    unique_in_order,
)

UMBRAL_SISTEMA = 0.80
UMBRALES_COMPLEMENTARIOS = (0.80, 0.8465, 0.876)
K = 5


def load_runs(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def load_gold(path, split="prueba"):
    with open(path, encoding="utf-8", newline="") as fh:
        return OrderedDict((r["id"], r) for r in csv.DictReader(fh) if r["split"] == split)


def _ratio(num, den):
    return num / den if den else None


def analyze(runs, gold, threshold=UMBRAL_SISTEMA, extra_thresholds=UMBRALES_COMPLEMENTARIOS, k=K):
    retrieve = {r["id"]: r for r in runs if r.get("fase") == "retrieve" and r["id"] in gold}
    asks = [r for r in runs if r.get("fase") == "ask" and r["id"] in gold]
    respondibles = [i for i, g in gold.items() if g["tipo"] != "no_respondible"]
    no_respondibles = [i for i, g in gold.items() if g["tipo"] == "no_respondible"]

    # ── Recuperación (independiente del modelo) ──
    def runs_for(ids):
        return [(unique_in_order(retrieve[i]["docs"]), {gold[i]["evidencia_doc_id"]}) for i in ids if i in retrieve]

    def rec_block(ids):
        rr = runs_for(ids)
        return {
            "n": len(rr),
            f"recall@{k}": mean_defined(recall_at_k(r, rel, k) for r, rel in rr),
            "mrr": mean_defined(reciprocal_rank(r, rel, k) for r, rel in rr),
            f"ndcg@{k}": mean_defined(ndcg_at_k(r, rel, k) for r, rel in rr),
        }

    recuperacion = rec_block(respondibles)
    recuperacion["resumen_retrieval_summary"] = retrieval_summary(runs_for(respondibles), ks=(1, 3, k))
    recuperacion["por_fuente"] = {f: rec_block([i for i in respondibles if gold[i]["fuente_esperada"] == f])
                                  for f in sorted({gold[i]["fuente_esperada"] for i in respondibles})}
    recuperacion["por_idioma"] = {l: rec_block([i for i in respondibles if gold[i]["idioma"] == l])
                                  for l in sorted({gold[i]["idioma"] for i in respondibles})}
    faltan_retrieve = [i for i in gold if i not in retrieve]

    # ── Generación por modelo ──
    generacion = OrderedDict()
    for model in dict.fromkeys(a["modelo"] for a in asks):
        by_id = {a["id"]: a for a in asks if a["modelo"] == model}
        ok = lambda a: a is not None and a.get("http") == 200  # noqa: E731
        corridas = list(by_id.values())
        errores = [{"id": a["id"], "http": a.get("http"), "segundos": a.get("segundos"),
                    "servicio": (a.get("error") or {}).get("servicio")} for a in corridas if not ok(a)]
        sin_corrida = [i for i in gold if i not in by_id]
        resp_runs = [by_id.get(i) for i in respondibles]
        nr_runs = [by_id.get(i) for i in no_respondibles]
        valid = sum(len(a.get("citas_validas", [])) for a in corridas if ok(a))
        invalid = sum(len(a.get("citas_invalidas", [])) for a in corridas if ok(a))
        con_cita = sum(1 for a in resp_runs if ok(a) and a.get("citas_validas"))
        cita_evidencia = sum(1 for a in resp_runs if ok(a) and a.get("evidencia_citada"))
        abst_indebida = sum(1 for a in resp_runs if ok(a) and a.get("abstained"))
        abst_correcta = sum(1 for a in nr_runs if ok(a) and a.get("abstained"))
        tiempos = [a["segundos"] for a in corridas if ok(a)]
        apr = abstention_precision_recall(
            [gold[i]["tipo"] == "no_respondible" for i in gold],
            [bool(ok(by_id.get(i)) and by_id[i].get("abstained")) for i in gold],
        )
        generacion[model] = {
            "corridas": len(corridas), "exitosas": len(tiempos), "errores": errores, "sin_corrida": sin_corrida,
            "respondibles": len(respondibles),
            "con_al_menos_una_cita_valida": con_cita,
            "pct_con_cita_valida": _ratio(con_cita, len(respondibles)),
            "cita_documento_evidencia": cita_evidencia,
            "pct_cita_documento_evidencia": _ratio(cita_evidencia, len(respondibles)),
            "abstencion_indebida_en_respondibles": abst_indebida,
            "citas_validas_total": valid, "citas_invalidas_total": invalid,
            "pct_citas_invalidas": _ratio(invalid, valid + invalid),
            "no_respondibles": len(no_respondibles), "abstencion_correcta": abst_correcta,
            "abstencion_precision": apr["precision"], "abstencion_recall": apr["recall"],
            "tiempo_medio_s": statistics.mean(tiempos) if tiempos else None,
            "tiempo_mediana_s": statistics.median(tiempos) if tiempos else None,
            "umbrales_registrados": sorted({a.get("threshold") for a in corridas if ok(a)}),
            "repeat_penalty_registrado": sorted({a.get("repeat_penalty") for a in corridas if ok(a)}),
        }

    # ── Umbrales alternativos: solo informativo ──
    max_score = {i: max(retrieve[i]["scores"]) for i in retrieve if retrieve[i]["scores"]}
    complementario = {
        "nota": "Informativo; no se usó para decidir el umbral del sistema (0,80). Usa el score máximo "
                "registrado en la fase retrieve de la partición de prueba.",
        "umbrales": [
            {"umbral": t,
             "respondibles_respondidas": sum(1 for i in respondibles if max_score.get(i, 0) >= t),
             "respondibles": len(respondibles),
             "no_respondibles_abstenidas": sum(1 for i in no_respondibles if max_score.get(i, 1) < t),
             "no_respondibles": len(no_respondibles)}
            for t in extra_thresholds
        ],
    }
    return {
        "particion": "prueba", "umbral_sistema": threshold, "k": k,
        "preguntas": len(gold), "respondibles": len(respondibles), "no_respondibles": len(no_respondibles),
        "faltan_registros_retrieve": faltan_retrieve,
        "recuperacion": recuperacion, "generacion": generacion,
        "analisis_complementario_no_usado_para_decision": complementario,
    }


def _fmt(v, pct=False):
    if v is None:
        return "-"
    return f"{v:.1%}" if pct else (f"{v:.3f}" if isinstance(v, float) else str(v))


def print_tables(res):
    r = res["recuperacion"]
    print(f"Recuperación (n={r['n']} respondibles de prueba, a nivel de documento): "
          f"""recall@{res['k']}={_fmt(r[f"recall@{res['k']}"])}  MRR={_fmt(r['mrr'])}  nDCG@{res['k']}={_fmt(r[f"ndcg@{res['k']}"])}""")
    for grupo in ("por_fuente", "por_idioma"):
        for key, b in r[grupo].items():
            print(f"  {key:12s} n={b['n']:2d}  recall@5={_fmt(b['recall@5'])}  MRR={_fmt(b['mrr'])}  nDCG@5={_fmt(b['ndcg@5'])}")
    print("\nModelo         n  err  cita≥1      cita_evid   citas_inv  abst_ok  abst_indeb  t_medio  t_mediana")
    for m, g in res["generacion"].items():
        print(f"{m:13s} {g['corridas']:2d}  {len(g['errores']):3d}  "
              f"{g['con_al_menos_una_cita_valida']:2d}/{g['respondibles']} {_fmt(g['pct_con_cita_valida'], True):>6s}  "
              f"{g['cita_documento_evidencia']:2d}/{g['respondibles']} {_fmt(g['pct_cita_documento_evidencia'], True):>6s}  "
              f"{g['citas_invalidas_total']}/{g['citas_validas_total'] + g['citas_invalidas_total']:<3d}      "
              f"{g['abstencion_correcta']}/{g['no_respondibles']}      {g['abstencion_indebida_en_respondibles']}/{g['respondibles']}   "
              f"{_fmt(g['tiempo_medio_s']):>7s}  {_fmt(g['tiempo_mediana_s']):>7s}")
        for e in g["errores"]:
            print(f"    error: {e['id']} http={e['http']} {e['segundos']}s servicio={e['servicio']}")
    print("\nAnálisis complementario de umbrales (informativo):")
    for u in res["analisis_complementario_no_usado_para_decision"]["umbrales"]:
        print(f"  t={u['umbral']:.4f}: respondidas {u['respondibles_respondidas']}/{u['respondibles']}  "
              f"no_resp abstenidas {u['no_respondibles_abstenidas']}/{u['no_respondibles']}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", default="data/experimento_prueba.jsonl")
    parser.add_argument("--gold", default="docs/gold_standard.csv")
    parser.add_argument("--salida", default="data/resultados_prueba.json")
    args = parser.parse_args(argv)
    res = analyze(load_runs(args.runs), load_gold(args.gold))
    Path(args.salida).parent.mkdir(parents=True, exist_ok=True)
    Path(args.salida).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print_tables(res)
    print(f"\nDetalle: {args.salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
