"""Experimento RAG robusto: acepta el gold de Abel (CSV) y el nuestro (JSONL), uno o los dos a la vez.

Cambios respecto a scripts/ejecutar_experimento.py:
  1. Recuperación con k=10 por defecto (--k-retrieve). El original usaba k=5 y luego se reportaba
     Recall@10, que con 5 resultados es igual a Recall@5. /ask usa --k-ask (5 por defecto).
  2. Varios documentos relevantes por pregunta (comparativas): la evidencia citada cuenta si se cita
     CUALQUIERA de los relevantes, y se reporta también la fracción de relevantes citados.
  3. Lee los dos formatos de gold y normaliza split (test=prueba, dev=desarrollo) y tipos
     (no_respondible=sin_evidencia).
  4. Revisa /health antes de empezar: si falta un modelo en Ollama (p. ej. llama3.2:3b) lo omite y
     avisa, en vez de llenar el archivo de errores.
  5. Se puede reanudar (--reanudar): omite lo que ya está registrado, sin repetir llamadas.
  6. Calcula las métricas al final (Recall@1/3/5/10, MRR, nDCG@10 a nivel documento; abstención;
     calibración del umbral en desarrollo y su efecto en prueba; resumen por modelo) y las guarda en JSON.
  7. --solo-retrieve: sin LLM, tarda segundos. Sirve para probar cambios de índice o de umbral.
  8. Solo usa la biblioteca estándar (no requiere 'requests'): corre dentro del contenedor o en el equipo.

Nunca guarda texto de preguntas, fragmentos ni respuestas, igual que el original.

Ejemplos (desde la carpeta del proyecto, con la API levantada):
  # Solo recuperación, los dos gold, rápido:
  python data/ejecutar_experimento_robusto.py --gold data/gold_standard.csv data/gold/gold.jsonl --solo-retrieve
  # Experimento completo (recuperación + /ask con los modelos disponibles) sobre la partición de prueba:
  python data/ejecutar_experimento_robusto.py --gold data/gold_standard.csv data/gold/gold.jsonl --salida data/experimento_robusto.jsonl
  # Reanudar si se cortó:
  python data/ejecutar_experimento_robusto.py --gold ... --salida data/experimento_robusto.jsonl --reanudar
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

MODELOS = ["gemma2:2b", "qwen2.5:1.5b", "llama3.2:1b", "llama3.2:3b"]
SPLITS = {"test": "prueba", "prueba": "prueba", "dev": "desarrollo", "desarrollo": "desarrollo",
          "train": "desarrollo"}
TIPOS_SIN_RESPUESTA = {"sin_evidencia", "no_respondible"}


# ----------------------------------------------------------------------------- gold
def _norm_split(valor):
    return SPLITS.get((valor or "").strip().lower(), (valor or "").strip().lower())


def leer_gold(ruta):
    """Devuelve una lista de preguntas normalizadas: id, pregunta, idioma, tipo, split, relevantes, abstener."""
    ruta = Path(ruta)
    filas = []
    if ruta.suffix.lower() == ".csv":  # formato de Abel
        with ruta.open(encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                rel = [r["evidencia_doc_id"]] if (r.get("evidencia_doc_id") or "").strip() else []
                tipo = r["tipo"].strip()
                filas.append({"id": r["id"], "pregunta": r["pregunta"], "idioma": r.get("idioma", ""),
                              "tipo": tipo, "split": _norm_split(r.get("split")), "relevantes": rel,
                              "abstener": tipo in TIPOS_SIN_RESPUESTA or not rel,
                              "origen": f"abel:{ruta.name}", "validada": r.get("validada_por", "")})
    else:  # nuestro gold.jsonl
        with ruta.open(encoding="utf-8") as fh:
            for linea in fh:
                if not linea.strip():
                    continue
                r = json.loads(linea)
                rel = list(r.get("documentos_relevantes") or [])
                tipo = r["tipo"]
                filas.append({"id": r["question_id"], "pregunta": r["pregunta"], "idioma": r.get("idioma", ""),
                              "tipo": tipo, "split": _norm_split(r.get("split")), "relevantes": rel,
                              "abstener": tipo in TIPOS_SIN_RESPUESTA or (not rel and tipo != "adversarial"),
                              "origen": f"nuestro:{ruta.name}", "validada": r.get("origen", "")})
    if not filas:
        raise SystemExit(f"{ruta} no tiene preguntas.")
    return filas


# ----------------------------------------------------------------------------- HTTP
def http_json(url, payload=None, timeout=120):
    datos = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=datos, headers={"Content-Type": "application/json"},
                                 method="POST" if payload is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read().decode("utf-8") or "{}")
        except ValueError:
            return exc.code, {}


# ----------------------------------------------------------------------------- métricas
def docs_unicos(docs):
    """Los fragmentos se colapsan a documentos conservando el primer rango."""
    vistos, salida = set(), []
    for d in docs:
        if d not in vistos:
            vistos.add(d)
            salida.append(d)
    return salida


def recall_at_k(docs, rel, k):
    return len(set(docs[:k]) & set(rel)) / len(rel)


def rr(docs, rel):
    for i, d in enumerate(docs, 1):
        if d in rel:
            return 1.0 / i
    return 0.0


def ndcg_at_k(docs, rel, k=10):
    dcg = sum(1.0 / math.log2(i + 1) for i, d in enumerate(docs[:k], 1) if d in rel)
    ideal = sum(1.0 / math.log2(i + 1) for i in range(1, min(len(rel), k) + 1))
    return dcg / ideal if ideal else 0.0


def media(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else None


def f(x, nd=3):
    return "-" if x is None else f"{x:.{nd}f}"


def tabla_retrieve(regs):
    """regs: registros 'retrieve' con relevantes no vacíos y que no deben abstenerse."""
    por_tipo = defaultdict(list)
    for r in regs:
        docs, rel = docs_unicos(r["docs"]), set(r["relevantes"])
        por_tipo[r["tipo"]].append((recall_at_k(docs, rel, 1), recall_at_k(docs, rel, 3),
                                    recall_at_k(docs, rel, 5), recall_at_k(docs, rel, 10),
                                    rr(docs, rel), ndcg_at_k(docs, rel, 10)))
    por_tipo["GLOBAL"] = [m for v in list(por_tipo.values()) for m in v]
    out = {}
    for t, v in por_tipo.items():
        out[t] = {"n": len(v), **{n: media(x[i] for x in v) for i, n in
                                  enumerate(["R@1", "R@3", "R@5", "R@10", "MRR", "nDCG@10"])}}
    return out


def prf(pred_abst, real_abst):
    vp = sum(p and a for p, a in zip(pred_abst, real_abst))
    fp = sum(p and not a for p, a in zip(pred_abst, real_abst))
    fn = sum((not p) and a for p, a in zip(pred_abst, real_abst))
    prec = vp / (vp + fp) if vp + fp else None
    rec = vp / (vp + fn) if vp + fn else None
    f1 = 2 * prec * rec / (prec + rec) if prec and rec else (0.0 if prec is not None and rec is not None else None)
    return {"vp": vp, "fp": fp, "fn": fn, "precision": prec, "recall": rec, "f1": f1}


def calibrar(regs_cal, rango=(0.60, 0.96)):
    """Umbral que maximiza F1 de abstención en las preguntas dadas (positivo = debe abstenerse)."""
    top = [(max(r["scores"]) if r["scores"] else 0.0, r["abstener"]) for r in regs_cal]
    if not any(a for _, a in top) or all(a for _, a in top):
        return None, None
    mejor = (None, -1.0)
    u = rango[0]
    while u <= rango[1] + 1e-9:
        m = prf([s < u for s, _ in top], [a for _, a in top])
        if (m["f1"] or 0.0) > mejor[1] + 1e-12:
            mejor = (round(u, 2), m["f1"] or 0.0)
        u += 0.01
    return mejor


def imprimir_tabla(tb):
    print(f"{'':16}{'n':>4}  {'R@1':>5} {'R@3':>5} {'R@5':>5} {'R@10':>5} {'MRR':>5} {'nDCG':>5}")
    for t in sorted(tb, key=lambda x: (x != "GLOBAL", x)):
        v = tb[t]
        print(f"{t:16}{v['n']:>4}  " + " ".join(f"{f(v[m]):>5}" for m in ["R@1", "R@3", "R@5", "R@10", "MRR", "nDCG@10"]))


# ----------------------------------------------------------------------------- principal
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--gold", nargs="+", required=True, help="uno o más archivos: .csv (Abel) o .jsonl (nuestro)")
    ap.add_argument("--api", default=os.getenv("RAG_API_URL", "http://localhost:8000"))
    ap.add_argument("--split", default="prueba", choices=["prueba", "desarrollo", "todos"],
                    help="partición que se evalúa (por defecto prueba)")
    ap.add_argument("--backend", choices=["milvus", "solr"], default="milvus",
                    help="motor de recuperación de la API (milvus denso o solr BM25)")
    ap.add_argument("--modelos", nargs="+", default=MODELOS)
    ap.add_argument("--k-retrieve", type=int, default=10, help="k de /retrieve (máx. 15)")
    ap.add_argument("--k-ask", type=int, default=5, help="k de /ask")
    ap.add_argument("--umbral", type=float, default=0.80, help="umbral para la tabla de abstención simulada")
    ap.add_argument("--calibrar-con", default="desarrollo", choices=["desarrollo", "todos"],
                    help="preguntas con las que se calibra el umbral (no se calibra con la partición evaluada)")
    ap.add_argument("--solo-retrieve", action="store_true", help="no llama a /ask (sin LLM)")
    ap.add_argument("--salida", default="data/experimento_robusto.jsonl")
    ap.add_argument("--resumen", default=None, help="JSON de métricas (por defecto: <salida>.resumen.json)")
    ap.add_argument("--reanudar", action="store_true", help="continúa un archivo existente sin repetir lo hecho")
    ap.add_argument("--reintentar-errores", action="store_true",
                    help="con --reanudar, vuelve a llamar a /ask solo en las corridas que fallaron (http distinto de 200); "
                         "el resumen usa el último registro de cada (modelo, pregunta)")
    ap.add_argument("--limite-s", type=float, default=7200)
    ap.add_argument("--timeout-ask", type=float, default=330)
    a = ap.parse_args(argv)

    api = a.api.rstrip("/")
    preguntas, ids = [], set()
    for ruta in a.gold:
        for p in leer_gold(ruta):
            if p["id"] in ids:
                raise SystemExit(f"id repetido entre gold: {p['id']}")
            ids.add(p["id"])
            preguntas.append(p)
    evaluar = [p for p in preguntas if a.split == "todos" or p["split"] == a.split]
    if a.calibrar_con == "todos":
        calibracion = preguntas
    else:
        calibracion = [p for p in preguntas if p["split"] == "desarrollo"]
    if not evaluar:
        raise SystemExit(f"No hay preguntas con split={a.split}.")
    # se recupera para evaluar + calibrar (una sola vez por pregunta)
    a_recuperar = {p["id"]: p for p in evaluar + calibracion}
    print(f"gold: {len(preguntas)} preguntas | a evaluar ({a.split}): {len(evaluar)} | "
          f"para calibrar ({a.calibrar_con}): {len(calibracion)} | recuperar: {len(a_recuperar)}")

    # --- estado de la API
    modelos = list(a.modelos)
    try:
        st, h = http_json(f"{api}/health?deep=true", timeout=30)
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"No se alcanza la API en {api}: {exc}")
    if st != 200 or h.get("status") != "ok":
        raise SystemExit(f"/health no está ok: {st} {h}")
    print(f"API ok | colección {h.get('collection')} | filas {h.get('milvus', {}).get('rows')} | backend {a.backend}"
          + (f" | solr {h.get('solr')}" if a.backend == "solr" else ""))
    if not a.solo_retrieve:
        disponibles = set(h.get("ollama", {}).get("models", []))
        faltan = [m for m in modelos if m not in disponibles]
        if faltan:
            print(f"AVISO: modelos no disponibles en Ollama, se omiten: {faltan}")
            modelos = [m for m in modelos if m in disponibles]
        if not modelos:
            raise SystemExit("Ningún modelo disponible. Use --solo-retrieve o instale un modelo.")

    salida = Path(a.salida)
    hecho = set()
    registros = []
    if salida.exists():
        if not a.reanudar:
            raise SystemExit(f"{salida} ya existe; use --reanudar o elija otra --salida.")
        for linea in salida.read_text(encoding="utf-8").splitlines():
            if linea.strip():
                r = json.loads(linea)
                registros.append(r)
                if a.reintentar_errores and r.get("fase") == "ask" and r.get("http") != 200:
                    continue  # se volverá a intentar
                hecho.add((r.get("fase"), r.get("modelo"), r.get("id")))
        print(f"reanudando: {len(registros)} registros ya existentes")
    salida.parent.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    with salida.open("a", encoding="utf-8") as out:
        def log(rec):
            registros.append(rec)
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            out.flush()

        # --- 1. recuperación
        for p in a_recuperar.values():
            if ("retrieve", None, p["id"]) in hecho:
                continue
            try:
                st, body = http_json(f"{api}/retrieve", {"question": p["pregunta"], "k": a.k_retrieve, "backend": a.backend})
            except Exception as exc:  # noqa: BLE001
                st, body = None, {"error": type(exc).__name__}
            frags = body.get("fragments", []) if st == 200 else []
            log({"fase": "retrieve", "id": p["id"], "tipo": p["tipo"], "idioma": p["idioma"], "split": p["split"],
                 "http": st, "relevantes": p["relevantes"], "abstener": p["abstener"],
                 "docs": [x["document_id"] for x in frags], "scores": [x["score"] for x in frags]})
        print("retrieve listo", flush=True)

        # --- 2. generación
        if not a.solo_retrieve:
            for modelo in modelos:
                for p in evaluar:
                    if ("ask", modelo, p["id"]) in hecho:
                        continue
                    if time.perf_counter() - t0 > a.limite_s:
                        log({"fase": "detenido", "motivo": f"más de {a.limite_s:.0f} s"})
                        print("DETENIDO por tiempo; use --reanudar para continuar", flush=True)
                        return _resumen(a, registros, evaluar, calibracion, modelos)
                    t1 = time.perf_counter()
                    rec = {"fase": "ask", "modelo": modelo, "id": p["id"], "tipo": p["tipo"], "split": p["split"],
                           "relevantes": p["relevantes"], "abstener": p["abstener"]}
                    try:
                        st, body = http_json(f"{api}/ask", {"question": p["pregunta"], "model": modelo,
                                                            "k": a.k_ask, "backend": a.backend}, timeout=a.timeout_ask)
                        rec["http"] = st
                        if st == 200:
                            ev = {e["ref"]: e for e in body.get("evidence", [])}
                            citados = [ev[c["ref"]]["document_id"] for c in body.get("citations", [])
                                       if c["ref"] in ev]
                            rel = set(p["relevantes"])
                            rec.update(abstained=body.get("abstained"), reason=body.get("abstention_reason"),
                                       citas_invalidas=body.get("invalid_citations"), docs_citados=citados,
                                       evidencia_citada=bool(rel) and bool(rel & set(citados)),
                                       frac_relevantes_citados=(len(rel & set(citados)) / len(rel)) if rel else None,
                                       respuesta_chars=len(body.get("answer", "")),
                                       timings=body.get("params", {}).get("timings"), usage=body.get("usage"),
                                       threshold=body.get("params", {}).get("score_threshold"))
                        else:
                            d = body.get("detail", {}) if isinstance(body, dict) else {}
                            rec["error"] = {k: str(v)[:160] for k, v in d.items()} if isinstance(d, dict) \
                                else {"detail": str(d)[:160]}
                    except Exception as exc:  # noqa: BLE001
                        rec.update(http=None, error={"excepcion": type(exc).__name__})
                    rec["segundos"] = round(time.perf_counter() - t1, 2)
                    log(rec)
                    print(f"{modelo} {p['id']} http={rec.get('http')} {rec['segundos']}s", flush=True)
    return _resumen(a, registros, evaluar, calibracion, modelos)


def _resumen(a, registros, evaluar, calibracion, modelos):
    ids_eval = {p["id"] for p in evaluar}
    ret = {r["id"]: r for r in registros if r.get("fase") == "retrieve"}
    r_eval = [ret[i] for i in ids_eval if i in ret and ret[i]["http"] == 200]
    errores_ret = [i for i in ids_eval if i in ret and ret[i]["http"] != 200]
    resumen = {"backend": a.backend, "split": a.split, "k_retrieve": a.k_retrieve, "n_evaluadas": len(evaluar),
               "errores_retrieve": errores_ret}

    print(f"\n=== RECUPERACIÓN (split={a.split}, k={a.k_retrieve}, nivel documento) ===")
    con_resp = [r for r in r_eval if r["relevantes"] and not r["abstener"]]
    tb = tabla_retrieve(con_resp)
    imprimir_tabla(tb)
    resumen["recuperacion"] = tb
    print("Nota: con k fragmentos se obtienen <= k documentos distintos; R@10 es un máximo posible, no exacto.")

    print(f"\n=== ABSTENCIÓN (positivo = debe abstenerse) ===")
    if a.backend == "solr":
        print("NOTA: con solr las puntuaciones son BM25 y no son comparables con el umbral de coseno; "
              "esta sección no es interpretable para Solr.")
    real = [r["abstener"] for r in r_eval]
    top = [max(r["scores"]) if r["scores"] else 0.0 for r in r_eval]
    m80 = prf([s < a.umbral for s in top], real)
    print(f"umbral fijo {a.umbral}: {m80}")
    resumen["abstencion_umbral_fijo"] = {"umbral": a.umbral, **m80}
    cal = [ret[p["id"]] for p in calibracion if p["id"] in ret and ret[p["id"]]["http"] == 200
           and p["id"] not in ids_eval]
    u, f1c = calibrar(cal)
    n_pos_cal = sum(r["abstener"] for r in cal)
    if u is None:
        print(f"calibración ({a.calibrar_con}, sin las evaluadas): no calculable "
              f"(n={len(cal)}, a abstener={n_pos_cal}; se necesitan ambas clases)")
        resumen["calibracion"] = None
    else:
        mc = prf([s < u for s in top], real)
        print(f"umbral calibrado en {a.calibrar_con} (n={len(cal)}, a abstener={n_pos_cal}, F1 dev={f1c:.3f}): {u} "
              f"-> en {a.split}: {mc}")
        resumen["calibracion"] = {"umbral": u, "n": len(cal), "positivos": n_pos_cal, "f1_calibracion": f1c, **mc}
        if n_pos_cal < 10:
            print(f"  ¡Cuidado! Solo {n_pos_cal} casos a abstener en calibración: el umbral es poco fiable.")
    barrido = []
    for k_u in range(60, 96, 2):
        mm = prf([s < k_u / 100 for s in top], real)
        barrido.append({"umbral": k_u / 100, **mm})
    resumen["barrido_umbral"] = barrido
    print("umbral  precisión recall  f1")
    for b in barrido[8:]:
        print(f"{b['umbral']:.2f}   {f(b['precision']):>6} {f(b['recall']):>6} {f(b['f1']):>6}")

    ultimo = {}
    for r in registros:  # si una corrida se reintentó, vale el último registro
        if r.get("fase") == "ask" and r["id"] in ids_eval:
            ultimo[(r["modelo"], r["id"])] = r
    asks = list(ultimo.values())
    if asks:
        print("\n=== GENERACIÓN POR MODELO ===")
        print(f"{'modelo':16}{'n':>4} {'http200':>8} {'abst_ok':>8} {'abst_mal':>9} {'cita_rel':>9} {'frac_rel':>9} {'seg':>7}")
        res_m = {}
        for m in modelos:
            rs = [r for r in asks if r["modelo"] == m]
            if not rs:
                continue
            ok = [r for r in rs if r.get("http") == 200]
            deben = [r for r in ok if r["abstener"]]
            pueden = [r for r in ok if not r["abstener"] and r["relevantes"]]
            abst_ok = media(1.0 if r["abstained"] else 0.0 for r in deben)
            abst_mal = media(1.0 if r["abstained"] else 0.0 for r in pueden)
            resp = [r for r in pueden if not r["abstained"]]
            cita = media(1.0 if r["evidencia_citada"] else 0.0 for r in resp)
            frac = media(r["frac_relevantes_citados"] for r in resp)
            seg = media(r["segundos"] for r in rs)
            res_m[m] = {"n": len(rs), "http200": len(ok) / len(rs), "abstencion_correcta": abst_ok,
                        "abstencion_indebida": abst_mal, "cita_relevante": cita, "frac_relevantes_citados": frac,
                        "segundos_medio": seg, "citas_invalidas": sum(1 for r in ok if r.get("citas_invalidas"))}
            print(f"{m:16}{len(rs):>4} {f(len(ok) / len(rs)):>8} {f(abst_ok):>8} {f(abst_mal):>9} "
                  f"{f(cita):>9} {f(frac):>9} {f(seg, 1):>7}")
        print("abst_ok: abstuvo cuando debía. abst_mal: abstuvo teniendo respuesta (queremos bajo).")
        print("cita_rel: entre las respondidas, citó algún documento relevante. frac_rel: fracción de relevantes citados.")
        resumen["modelos"] = res_m

    destino = Path(a.resumen or str(a.salida) + ".resumen.json")
    destino.write_text(json.dumps(resumen, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nEscrito: {a.salida} y {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
