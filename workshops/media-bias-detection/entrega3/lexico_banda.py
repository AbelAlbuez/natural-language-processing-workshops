"""Elección léxica en la banda de similitud 0,65–0,80: ¿el mismo hecho contado distinto?

`lexico.py` mide las diferencias de palabras dentro de eventos con similitud
≥ 0,80. Ese umbral favorece titulares redactados de forma parecida, así que el
encuadre muy distinto de un mismo hecho queda fuera (cota inferior). Aquí se
repite el análisis con las parejas recíprocas entre medios de la banda
0,65 ≤ sim < 0,80, donde debería estar «el mismo hecho contado distinto». El
problema es que en esa banda la mayoría de las parejas NO son el mismo hecho
(precisión ponderada 25–63 % por tramo, calibracion.py): sin más, se medirían
diferencias de agenda como si fueran de encuadre.

    1. Unidad: parejas recíprocas entre medios (± 2 días, fecha al día, sin
       plantillas masivas, criterio de eventos.py) con 0,65 ≤ sim < 0,80 que no
       estén ya en un mismo evento ≥ 0,80.
    2. Filtro de precisión: una regla simple (misma fecha, términos raros
       compartidos, mismo tópico) elegida en una rejilla por la cota inferior de
       Wilson de su precisión sobre las parejas anotadas de la calibración. La
       precisión se mide con esas anotaciones (Wilson y ponderada por población),
       y la del PROCEDIMIENTO de elección con validación cruzada anidada. Como
       sensibilidad, un logístico entrenado con todas las anotaciones.
    3. Log-odds con prior informativo emparejado (el medio frente al otro medio
       de la pareja) y formas de nombrar al gobierno, con las funciones de
       lexico.py; comparación con los resultados ≥ 0,80.
    4. Ejemplos lado a lado (ejemplos_banda.md).
    5. Robustez: bootstrap por meses, sin RCN como contraparte, ventana común en
       Duque, sin filtro (toda la banda), filtro logístico, y las parejas que el
       filtro rechaza como diagnóstico de agenda.

Uso: SCRIPT=lexico_banda.py ./run.sh - --output resultados_publico
"""

from __future__ import annotations

import argparse
import itertools
import logging
import time
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter
from scipy.stats import spearmanr

import eventos
from calibracion import ETIQUETAS, combine_personas, tramo, weighted_precision
from core import normalize, tokenize
from figuras import (AXIS, FUENTE, GOV_COLORS, GOV_NAMES, INK2, MEDIA_NAMES, MUTED, SHORT, SURFACE, _margins,
                     _save, miles)
from lexico import (RCN, TEMAS_EXTERIOR, UMBRAL_CONTAGIO_FORMATO, _props_celda, clase_termino, comparar,
                    contagio_formato, matriz_formas, matriz_terminos, newcombe, precision_fecha_rcn,
                    proporciones_emparejadas, recorte_rcn, stop_lexico)
from research_stats import wilson_interval
from topics import GOVS, MEDIA, save_json

HERE = Path(__file__).resolve().parent
BANDA = (0.65, 0.80)
TRAMOS_BANDA = ["0.65–0.70", "0.70–0.75", "0.75–0.80"]
POSITIVA = ETIQUETAS[0]  # «Mismo hecho»
# Rejilla de reglas del filtro. Un término «raro» es un unigrama de contenido que
# aparece en ≤ df_raro titulares del corpus (304 mil): casi siempre un nombre
# propio, un lugar, una institución o un objeto concreto («otoniel», «tuchin»,
# «endeudamiento»). Exigirlo fija la ENTIDAD del hecho sin exigir que el resto de
# la redacción coincida.
DF_RAROS = (300, 1000, 3000)
REJILLA = {"dias_max": (0, 1, 2), "df_raro": DF_RAROS, "n_raro_min": (0, 1, 2), "mismo_topico": (False, True)}
# Rasgos del logístico (sensibilidad).
RASGOS_LOGIT = ["sim", "misma_fecha", "dos_dias", "wjac", "sum_idf", "n_raro_1000"]
VARIANTES = {
    "filtrada": "banda, filtro de la regla (principal)",
    "sin_filtro": "banda completa, sin filtro",
    "rechazada": "banda, parejas que el filtro rechaza (diagnóstico de agenda)",
    "logistica": "banda, filtro logístico p ≥ 0,5 (sensibilidad)",
}
NOTA_BANDA = "Parejas recíprocas entre medios con similitud 0,65–0,80 (± 2 días), fuera de los eventos ≥ 0,80."


# ── parejas y rasgos ─────────────────────────────────────────────────────────


def evento_de_titular(frame: pd.DataFrame, ev: pd.DataFrame) -> np.ndarray:
    """event_id (núcleo o seguimiento) de cada fila de `frame`, −1 si no está en ningún evento ≥ 0,80."""
    m = dict(zip(ev["article_id"], ev["event_id"]))
    return frame["article_id"].map(m).fillna(-1).astype(int).to_numpy()


def parejas_banda(pi, pj, ps, ev_de, lo=BANDA[0], hi=BANDA[1]) -> pd.DataFrame:
    """Parejas recíprocas con lo ≤ sim < hi que no están ya juntas en un mismo evento."""
    sel = (ps >= lo) & (ps < hi)
    i, j, s = pi[sel], pj[sel], ps[sel]
    mismo = (ev_de[i] >= 0) & (ev_de[i] == ev_de[j])
    return pd.DataFrame({"i": i[~mismo], "j": j[~mismo], "sim": s[~mismo].astype(float)})


def idf_titulares(sets: list[set[str]]) -> dict[str, tuple[int, float]]:
    """Frecuencia de documento e IDF (log N/df) de cada unigrama en los titulares."""
    df = Counter()
    for s in sets:
        df.update(s)
    n = len(sets)
    return {w: (c, float(np.log(n / c))) for w, c in df.items()}


def rasgos_pareja(a: set[str], b: set[str], idf: dict) -> dict:
    """Rasgos léxicos de una pareja de titulares (conjuntos de unigramas sin stopwords)."""
    comunes, union = a & b, a | b
    pesos = [idf[w][1] for w in comunes]
    tot = sum(idf[w][1] for w in union)
    out = {"n_comunes": len(comunes), "sum_idf": float(sum(pesos)), "max_idf": float(max(pesos, default=0.0)),
           "wjac": float(sum(pesos) / tot) if tot else 0.0,
           "jac": len(comunes) / len(union) if union else 0.0}
    for d in DF_RAROS:
        out[f"n_raro_{d}"] = sum(idf[w][0] <= d for w in comunes)
    # Jaccard de las palabras NO raras: mide si el resto de la redacción coincide
    norm_a, norm_b = {w for w in a if idf[w][0] > DF_RAROS[-1]}, {w for w in b if idf[w][0] > DF_RAROS[-1]}
    u = norm_a | norm_b
    out["jac_no_raras"] = len(norm_a & norm_b) / len(u) if u else 0.0
    return out


def tabla_rasgos(P: pd.DataFrame, sets, idf, day, topic) -> pd.DataFrame:
    R = pd.DataFrame([rasgos_pareja(sets[i], sets[j], idf) for i, j in zip(P["i"], P["j"])], index=P.index)
    R["sim"] = P["sim"].to_numpy()
    R["dias"] = np.abs(day[P["i"]] - day[P["j"]])
    R["misma_fecha"] = (R["dias"] == 0).astype(float)
    R["dos_dias"] = (R["dias"] == 2).astype(float)
    R["mismo_topico"] = topic[P["i"]] == topic[P["j"]]
    return R


# ── filtro ───────────────────────────────────────────────────────────────────


def reglas() -> list[dict]:
    """Rejilla de reglas (sin duplicados: con n_raro_min = 0 el df_raro no importa)."""
    out, vistos = [], set()
    for d, f, k, t in itertools.product(*REJILLA.values()):
        clave = (d, f if k else 0, k, t)
        if clave not in vistos:
            vistos.add(clave)
            out.append({"dias_max": d, "df_raro": f, "n_raro_min": k, "mismo_topico": t})
    return out


def aplica_regla(R: pd.DataFrame, r: dict) -> np.ndarray:
    m = (R["dias"] <= r["dias_max"]).to_numpy() & (R[f"n_raro_{r['df_raro']}"] >= r["n_raro_min"]).to_numpy()
    if r["mismo_topico"]:
        m &= R["mismo_topico"].to_numpy()
    return m


def describe_regla(r: dict) -> str:
    partes = ["misma fecha" if r["dias_max"] == 0 else f"≤ {r['dias_max']} día(s) de diferencia"]
    if r["n_raro_min"]:
        partes.append(f"≥ {r['n_raro_min']} término(s) compartido(s) que aparece(n) en ≤ {miles(r['df_raro'])} "
                      "titulares del corpus")
    if r["mismo_topico"]:
        partes.append("mismo tópico de BERTopic")
    return " + ".join(partes)


def elegir_regla(R: pd.DataFrame, y: np.ndarray, todas: list[dict], min_pasan: int = 8) -> int:
    """Índice de la regla con mayor cota inferior de Wilson de la precisión (equilibra
    precisión y número de parejas anotadas que pasan; al menos `min_pasan`)."""
    mejor, idx = -1.0, 0
    for k, r in enumerate(todas):
        m = aplica_regla(R, r)
        n = int(m.sum())
        if n < min_pasan:
            continue
        lo = wilson_interval(int(y[m].sum()), n)[0]
        if lo > mejor + 1e-12:
            mejor, idx = lo, k
    return idx


def precision_anidada(R: pd.DataFrame, y: np.ndarray, todas: list[dict], folds=5, reps=200, seed=42) -> dict:
    """Precisión honesta del PROCEDIMIENTO «elegir la regla en la rejilla y aplicarla»:
    se elige en k − 1 partes y se mide en la parte que queda (estratificado por la
    etiqueta), repetido `reps` veces. Devuelve la precisión agrupada fuera de la
    muestra (mediana y percentiles 2,5–97,5 entre repeticiones) y la cobertura."""
    rng = np.random.default_rng(seed)
    precs, cobs, elegidas = [], [], Counter()
    for _ in range(reps):
        fold = np.empty(len(y), dtype=int)
        for clase in (False, True):
            idx = rng.permutation(np.flatnonzero(y == clase))
            fold[idx] = np.arange(len(idx)) % folds
        pasa = np.zeros(len(y), dtype=bool)
        for f in range(folds):
            tr, te = fold != f, fold == f
            k = elegir_regla(R[tr], y[tr], todas, min_pasan=max(4, int(8 * tr.mean())))
            elegidas[k] += 1
            pasa[te] = aplica_regla(R[te], todas[k])
        if pasa.any():
            precs.append(y[pasa].mean())
        cobs.append(pasa.mean())
    precs = np.array(precs)
    return {"precision_mediana": float(np.median(precs)), "precision_media": float(precs.mean()),
            "p2_5": float(np.quantile(precs, 0.025)), "p97_5": float(np.quantile(precs, 0.975)),
            "cobertura_media": float(np.mean(cobs)), "repeticiones": reps, "partes": folds,
            "regla_mas_elegida": describe_regla(todas[elegidas.most_common(1)[0][0]]),
            "frac_veces_regla_mas_elegida": elegidas.most_common(1)[0][1] / (reps * folds)}


def logistica_oof(Ra: pd.DataFrame, y: np.ndarray, folds=5, reps=20, seed=42) -> tuple[np.ndarray, object]:
    """Probabilidades fuera de la muestra (validación cruzada repetida) de un
    logístico con `RASGOS_LOGIT`, entrenado con TODAS las parejas anotadas (todos
    los tramos: la similitud es un rasgo). Devuelve también el modelo ajustado con
    todo, para aplicarlo a la población."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import RepeatedStratifiedKFold
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    X = Ra[RASGOS_LOGIT].to_numpy(float)
    modelo = lambda: make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))  # noqa: E731
    suma, cuenta = np.zeros(len(y)), np.zeros(len(y))
    for tr, te in RepeatedStratifiedKFold(n_splits=folds, n_repeats=reps, random_state=seed).split(X, y):
        suma[te] += modelo().fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]
        cuenta[te] += 1
    return suma / cuenta, modelo().fit(X, y)


def precision_filtro(nombre: str, pasa: np.ndarray, A: pd.DataFrame, poblacion: pd.Series) -> dict:
    """Precisión de un filtro sobre las parejas anotadas de la banda: Wilson sin
    ponderar y ponderada por la población de parejas que pasan en cada tramo (como
    calibracion.weighted_precision)."""
    y = A["acierto"].to_numpy()
    k, n = int(y[pasa].sum()), int(pasa.sum())
    lo, hi = wilson_interval(k, n) if n else (np.nan, np.nan)
    pond = weighted_precision(A[pasa], poblacion)
    pond = pond[np.isclose(pond["umbral"], BANDA[0])]
    fila = {"filtro": nombre, "anotadas_banda": len(y), "pasan": n, "mismo_hecho": k,
            "precision": k / n if n else np.nan, "ic_bajo": lo, "ic_alto": hi,
            "recall_mismo_hecho": k / max(1, int(y.sum())),
            "precision_ponderada": float(pond["precision"].iat[0]) if len(pond) else np.nan,
            "ic_bajo_ponderada": float(pond["ic_bajo"].iat[0]) if len(pond) else np.nan,
            "ic_alto_ponderada": float(pond["ic_alto"].iat[0]) if len(pond) else np.nan,
            "parejas_poblacion": int(poblacion.sum())}
    for t in TRAMOS_BANDA:
        g = A["tramo"].to_numpy() == t
        fila[f"pasan_{t}"] = int((pasa & g).sum())
        fila[f"precision_{t}"] = float(y[pasa & g].mean()) if (pasa & g).any() else np.nan
    return fila


# ── tabla larga de parejas ───────────────────────────────────────────────────


def tabla_larga(P: pd.DataFrame, frame: pd.DataFrame) -> pd.DataFrame:
    """Dos filas por pareja (una por titular), con el formato que esperan las
    funciones de lexico.py: event_id = id de la pareja, source_id, title, texto,
    gobierno, fecha_inicio (la primera fecha de la pareja) y mes. Las parejas que
    cruzan el cambio de gobierno se descartan."""
    gob = frame["government_id"].to_numpy()
    fecha = frame["fecha"].to_numpy()
    ok = gob[P["i"]] == gob[P["j"]]
    P = P[ok]
    filas = []
    for lado in ("i", "j"):
        idx = P[lado].to_numpy()
        filas.append(pd.DataFrame({
            "event_id": P["pareja"].to_numpy(), "lado": lado, "fila": idx,
            "source_id": frame["source_id"].to_numpy()[idx], "title": frame["title"].to_numpy()[idx],
            "gobierno": gob[idx], "topic": frame["topic"].to_numpy()[idx], "sim": P["sim"].to_numpy(),
            "fecha_inicio": np.minimum(fecha[P["i"]], fecha[P["j"]]),
            "variante": P["variante"].to_numpy(), "logit": P["logit"].to_numpy()}))
    L = pd.concat(filas, ignore_index=True).sort_values(["event_id", "lado"], kind="stable").reset_index(drop=True)
    L["texto"] = L["title"].map(normalize)
    L["mes"] = pd.to_datetime(L["fecha_inicio"]).dt.to_period("M").astype(str)
    L["fecha_inicio"] = pd.to_datetime(L["fecha_inicio"]).dt.strftime("%Y-%m-%d")
    exterior = L.groupby("event_id")["topic"].transform(lambda s: s.isin(TEMAS_EXTERIOR).any())
    L["domestico"] = ~exterior
    return L


# ── análisis ─────────────────────────────────────────────────────────────────


def log_odds_variante(L, X, vocab, prior, rcn_desde, args, robustez: bool, sets=None) -> pd.DataFrame:
    """Log-odds del medio frente al otro medio de cada pareja, por medio × gobierno.
    Con `robustez`: bootstrap por meses, sin RCN como contraparte y ventana común."""
    filas = []
    for g in GOVS:
        for m in MEDIA:
            base = recorte_rcn(L[L["gobierno"] == g], m, g, rcn_desde)
            reps = args.reps if robustez else args.reps_variantes
            tab, n = comparar(base, X[base.index], vocab, prior, m, reps=reps, seed=args.seed,
                              min_eventos=args.min_eventos, meses=robustez)
            if tab is None:
                continue
            tab.insert(0, "parejas", n)
            tab.insert(0, "gobierno", g)
            tab.insert(0, "medio", m)
            if robustez:
                rob = {"sinrcn": (base, (RCN,) if m != RCN else None)}
                if g == "duque":
                    rob["ventana"] = (base[pd.to_datetime(base["fecha_inicio"]) >= rcn_desde], ())
                for nombre, (sub, excl) in rob.items():
                    r = None if excl is None else comparar(sub, X[sub.index], vocab, prior, m, excluir=excl,
                                                           reps=args.reps_variantes, seed=args.seed + 7,
                                                           min_eventos=1, meses=False)[0]
                    if r is None:
                        tab[f"delta_{nombre}"], tab[f"z_{nombre}"] = np.nan, np.nan
                        continue
                    r = r.set_index("termino").reindex(tab["termino"])
                    tab[f"delta_{nombre}"], tab[f"z_{nombre}"] = r["delta"].to_numpy(), r["z"].to_numpy()
                for c in ("delta_ventana", "z_ventana"):
                    if c not in tab:
                        tab[c] = np.nan
                cont = contagio_formato([sets[i] for i in base.index[base["source_id"] == m]])
                tab["frac_con_firma_programa"] = tab["termino"].map(cont).fillna(0.0)
            filas.append(tab)
    res = pd.concat(filas, ignore_index=True)
    res["clase"] = res["termino"].map(clase_termino)
    if "frac_con_firma_programa" in res:
        res.loc[res["frac_con_firma_programa"] >= UMBRAL_CONTAGIO_FORMATO, "clase"] = "formato"
    res["distintiva"] = ((res["delta"] > 0) & (res["q_bh"] < 0.05) & (res["n_eventos_medio"] >= args.min_eventos)
                         & (res["n_solo_medio"] >= args.min_discordantes))
    res["evitada"] = ((res["delta"] < 0) & (res["q_bh"] < 0.05) & (res["n_eventos_otros"] >= args.min_eventos)
                      & (res["n_solo_otros"] >= args.min_discordantes))
    if robustez:
        sig = lambda c: res[c].fillna(np.inf) >= 1.96  # noqa: E731  (NaN = la prueba no aplica)
        res["robusta"] = res["distintiva"] & (res["z_mes"] >= 1.96) & sig("z_sinrcn")
    return res


def comparar_con_080(lo: pd.DataFrame, lo80: pd.DataFrame, otras: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Agrega a cada término de la banda su resultado ≥ 0,80 (lexico.py) y su δ en
    las otras variantes. `nueva` = distintiva en la banda y no en ≥ 0,80."""
    ref = lo80.set_index(["medio", "gobierno", "termino"])
    clave = pd.MultiIndex.from_frame(lo[["medio", "gobierno", "termino"]])
    lo = lo.copy()
    lo["en_vocab_080"] = clave.isin(ref.index)
    r = ref.reindex(clave)
    lo["delta_080"] = r["delta"].to_numpy()
    lo["z_080"] = r["z"].to_numpy()
    lo["distintiva_080"] = r["distintiva"].astype("boolean").fillna(False).to_numpy(bool)
    lo["robusta_080"] = r["robusta"].astype("boolean").fillna(False).to_numpy(bool)
    lo["nueva"] = lo["distintiva"] & ~lo["distintiva_080"]
    # estricta: con ≥ 0,80 ni siquiera era nominalmente significativa (z < 1,96 o fuera del vocabulario)
    lo["nueva_estricta"] = lo["nueva"] & ~(lo["z_080"].fillna(0) >= 1.96)
    for nombre, t in otras.items():
        o = t.set_index(["medio", "gobierno", "termino"]).reindex(clave)
        lo[f"delta_{nombre}"] = o["delta"].to_numpy()
        lo[f"z_{nombre}"] = o["z"].to_numpy()
    # agenda: si el término también separa al medio en las parejas que el filtro
    # rechaza (mayoría de hechos distintos), es más un rasgo de la casa o de su
    # agenda que una forma de contar el mismo hecho
    lo["tambien_en_rechazadas"] = lo["z_rechazada"].fillna(0) >= 1.96
    return lo


def resumen_celdas(lo: pd.DataFrame, lo80: pd.DataFrame) -> pd.DataFrame:
    filas = []
    for (m, g), t in lo.groupby(["medio", "gobierno"], sort=False):
        d = t[t["distintiva"]]
        dc = d[d["clase"] == "contenido"]
        t80 = lo80[(lo80["medio"] == m) & (lo80["gobierno"] == g)]
        d80c = t80[t80["distintiva"] & (t80["clase"] == "contenido")]
        comun = t.dropna(subset=["delta_080"])
        filas.append({
            "medio": m, "gobierno": g, "parejas": int(t["parejas"].iat[0]), "terminos": len(t),
            "distintivas": len(d), "distintivas_contenido": len(dc), "robustas_contenido": int(dc["robusta"].sum()),
            "nuevas_contenido": int(dc["nueva"].sum()), "nuevas_contenido_robustas": int((dc["nueva"] & dc["robusta"]).sum()),
            "nuevas_estrictas_contenido_robustas": int((dc["nueva_estricta"] & dc["robusta"]).sum()),
            "nuevas_estrictas_robustas_no_en_rechazadas": int((dc["nueva_estricta"] & dc["robusta"]
                                                                & ~dc["tambien_en_rechazadas"]).sum()),
            "distintivas_contenido_080": len(d80c),
            "contenido_080_que_repiten": int(dc["distintiva_080"].sum()),
            "terminos_comunes_080": len(comun),
            "spearman_delta_080": float(spearmanr(comun["delta"], comun["delta_080"])[0]) if len(comun) > 2 else np.nan,
            "spearman_delta_sin_filtro": float(spearmanr(t["delta"], t["delta_sin_filtro"], nan_policy="omit")[0]),
            "spearman_delta_logistica": float(spearmanr(t["delta"], t["delta_logistica"], nan_policy="omit")[0]),
            "pct_distintivas_z_mes_196": 100 * float((d["z_mes"] >= 1.96).mean()) if len(d) else np.nan,
            "pct_distintivas_z_sinrcn_196": 100 * float((d["z_sinrcn"] >= 1.96).mean())
            if len(d) and m != RCN else np.nan,
            "pct_distintivas_z_ventana_196": 100 * float((d["z_ventana"] >= 1.96).mean())
            if len(d) and g == "duque" else np.nan,
            "spearman_delta_ventana": float(spearmanr(t["delta"], t["delta_ventana"], nan_policy="omit")[0])
            if g == "duque" else np.nan,
            "pct_distintivas_sin_filtro_z_196": 100 * float((d["z_sin_filtro"] >= 1.96).mean()) if len(d) else np.nan,
        })
    return pd.DataFrame(filas)


def formas_variante(L, F, rcn_desde, args, variante: str) -> pd.DataFrame:
    """Formas de nombrar: el medio frente al otro medio de la pareja (bootstrap por
    parejas), en parejas domésticas; con y sin RCN como contraparte, y ventana común."""
    dom = L[L["domestico"]]
    filas = []
    for g in GOVS:
        for m in MEDIA:
            base = recorte_rcn(dom[dom["gobierno"] == g], m, g, rcn_desde)
            casos = [("todos", base, ()), ("sin_rcn", base, (RCN,))]
            if g == "duque":
                casos.append(("ventana_comun", base[pd.to_datetime(base["fecha_inicio"]) >= rcn_desde], ()))
            for etiqueta, sub, excl in casos:
                if etiqueta == "sin_rcn" and m == RCN:
                    continue
                r = proporciones_emparejadas(sub, F.loc[sub.index], m, excluir=excl, reps=args.reps_formas,
                                             seed=args.seed)
                if r.empty:
                    continue
                r.insert(0, "otros", etiqueta)
                r.insert(0, "gobierno", g)
                r.insert(0, "medio", m)
                r.insert(0, "variante", variante)
                filas.append(r)
    return pd.concat(filas, ignore_index=True)


def formas_props(L, F, rcn_desde) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Proporción de cada forma en los titulares únicos del medio (parejas
    domésticas filtradas), IC de Wilson, y cambio Duque → Petro (Newcombe)."""
    dom = L[L["domestico"]]
    props = []
    for g in GOVS:
        for m in MEDIA:
            base = recorte_rcn(dom[dom["gobierno"] == g], m, g, rcn_desde)
            own = base[base["source_id"] == m].drop_duplicates("fila")
            props += _props_celda(own, F, m, g, "principal")
    props = pd.DataFrame(props)
    cambio = []
    for m in MEDIA:
        for c in ("gobierno_apellido", "pers_gobierno", "personal_amplio"):
            a = props[(props["medio"] == m) & (props["forma"] == c)].set_index("gobierno")
            if not a.loc["duque", "titulares"] or not a.loc["petro", "titulares"]:
                continue
            d, lo, hi = newcombe(a.loc["duque", "con_forma"], a.loc["duque", "titulares"],
                                 a.loc["petro", "con_forma"], a.loc["petro", "titulares"])
            cambio.append({"medio": m, "forma": c, "prop_duque": a.loc["duque", "prop"],
                           "prop_petro": a.loc["petro", "prop"], "cambio": d, "ic_bajo": lo, "ic_alto": hi,
                           "n_duque": a.loc["duque", "titulares"], "n_petro": a.loc["petro", "titulares"]})
    return props, pd.DataFrame(cambio)


def solapamiento(R: pd.DataFrame, etiqueta: str) -> dict:
    return {"conjunto": etiqueta, "parejas": len(R), "jaccard_medio": float(R["jac"].mean()),
            "jaccard_no_raras_medio": float(R["jac_no_raras"].mean()),
            "pct_misma_fecha": float(100 * R["misma_fecha"].mean()), "sim_media": float(R["sim"].mean())}


# ── ejemplos ─────────────────────────────────────────────────────────────────


def _pareja_md(L: pd.DataFrame, k: int, resaltar: str | None = None, nota: str = "") -> list[str]:
    p = L[L["event_id"] == k].sort_values("source_id", key=lambda s: s.map(MEDIA.index))
    r0 = p.iloc[0]
    lines = [f"**Pareja {k}** · {r0['fecha_inicio']} · similitud {r0['sim']:.2f}".replace(".", ",", 1)
             + (f" · {nota}" if nota else ""), "", "| Medio | Titular |", "|---|---|"]
    for r in p.itertuples():
        nombre = MEDIA_NAMES[r.source_id]
        lines.append(f"| {'**' + nombre + '**' if r.source_id == resaltar else nombre} | {r.title} |")
    return lines + [""]


def ejemplos_md(L, sets_l, lo, F, R_pob, A, frame, regla_txt, prec, seed) -> str:
    rng = np.random.default_rng(seed)
    Lf = L[L["variante"] == "filtrada"]
    lines = [
        "# Ejemplos: el mismo hecho contado distinto (banda 0,65–0,80, filtrada)", "",
        "Titulares reconstruidos desde la URL (sin tildes, cifras ni puntuación). Cada tabla es una pareja recíproca",
        f"de dos medios con similitud 0,65–0,80 que pasa el filtro ({regla_txt}).",
        f"**El filtro acierta el mismo hecho en el {100 * prec['precision']:.0f} % de las parejas anotadas que pasan "
        f"(IC 95 % {100 * prec['ic_bajo']:.0f}–{100 * prec['ic_alto']:.0f} %)**: alguna pareja de esta lista puede ser",
        f"dos hechos distintos. Semilla {seed}.", "",
        "## 1. Parejas anotadas a mano que pasan el filtro", "",
        "Todas las parejas de la calibración en la banda que pasan el filtro, con la etiqueta de la anotación. Sirven",
        "para ver qué clase de errores deja pasar.", "",
        "| Sim. | Días | Etiqueta | Titular A | Titular B |", "|---:|---:|---|---|---|",
    ]
    for r in A[A["pasa"]].sort_values("similitud").itertuples():
        lines.append(f"| {r.similitud:.2f} | {r.dias} | {r.etiqueta} | {frame['title'].iat[r.i]} | "
                     f"{frame['title'].iat[r.j]} |".replace(".", ",", 1))
    lines += ["", "## 2. Palabras distintivas nuevas (no salían con ≥ 0,80)", "",
              "Para cada medio y gobierno, hasta dos términos de contenido distintivos y robustos en la banda filtrada",
              "que en los eventos ≥ 0,80 no eran ni siquiera significativos (z < 1,96), y una pareja en la que el medio usa el término y el otro",
              "medio no.", ""]
    nuevas = lo[lo["nueva_estricta"] & lo["robusta"] & (lo["clase"] == "contenido")]
    for g in GOVS:
        bloque = []
        for m in MEDIA:
            top = nuevas[(nuevas["medio"] == m) & (nuevas["gobierno"] == g)].sort_values("z", ascending=False).head(2)
            for r in top.itertuples():
                part = Lf[(Lf["gobierno"] == g)]
                own = part[(part["source_id"] == m).to_numpy() & np.array([r.termino in sets_l[i] for i in part.index])]
                cand = []
                for k in own["event_id"].unique():
                    otro = part[(part["event_id"] == k) & (part["source_id"] != m)]
                    if len(otro) and r.termino not in sets_l[otro.index[0]]:
                        cand.append(k)
                if not cand:
                    continue
                agenda = " (también separa al medio en las parejas rechazadas: posible rasgo de la casa)" \
                    if r.tambien_en_rechazadas else ""
                bloque += [(f"*{MEDIA_NAMES[m]} · «{r.termino}»*: {100 * r.frac_medio:.1f} % de sus titulares frente al "
                            f"{100 * r.frac_otros:.1f} % del otro medio (log-odds {r.delta:+.2f}, z {r.z:.1f}; "
                            f"≥ 0,80: z {r.z_080:.1f}){agenda}.").replace(".", ",").replace("z nan", "no evaluado")
                           .replace("),", ")."), ""]
                bloque += _pareja_md(L, int(rng.choice(cand)), resaltar=m)
        if bloque:
            lines += [f"### Gobierno {GOV_NAMES[g]}", ""] + bloque
    lines += ["## 3. «Gobierno Petro/Duque» frente a «el Gobierno» en la misma pareja", "",
              "Parejas domésticas filtradas en las que un medio escribe el apellido del presidente junto a «Gobierno» y",
              "el otro escribe «Gobierno» o «Gobierno nacional» sin él.", ""]
    dom = Lf[Lf["domestico"]]
    for g in GOVS:
        part = dom[dom["gobierno"] == g]
        fp = F.loc[part.index]
        per = part.assign(p=fp["gobierno_apellido"].to_numpy(),
                          i=((fp["gobierno_nacional"] | fp["gobierno_generico"]) & ~fp["gobierno_apellido"]).to_numpy())
        agg = per.groupby("event_id")[["p", "i"]].any()
        ks = agg[agg["p"] & agg["i"]].index.to_numpy()
        lines += [f"### Gobierno {GOV_NAMES[g]} ({len(ks)} parejas con los dos usos)", ""]
        for k in rng.permutation(ks)[:4]:
            lines += _pareja_md(L, int(k))
    lines += ["## 4. Misma entidad, otra redacción", "",
              "Parejas filtradas con el menor solapamiento de las palabras no raras (Jaccard ≤ 0,10): comparten el",
              "nombre propio o el lugar, pero el resto del titular es distinto. Ocho al azar.", ""]
    Rf = R_pob[R_pob["variante"] == "filtrada"]
    ks = Rf.loc[Rf["jac_no_raras"] <= 0.10, "pareja"].to_numpy()
    en_lf = set(Lf["event_id"])
    ks = [k for k in rng.permutation(ks) if k in en_lf][:8]
    for k in ks:
        lines += _pareja_md(L, int(k))
    return "\n".join(lines)


# ── figuras (33 a 35) ────────────────────────────────────────────────────────


def fig_filtro(prec: pd.DataFrame, A: pd.DataFrame, pob: pd.DataFrame, res: Path, regla_txt: str, anidada: dict):
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.2), gridspec_kw={"width_ratios": [1.35, 1]})
    ax = axes[0]
    series = [("sin filtro", np.ones(len(A), bool), MUTED), ("regla (principal)", A["pasa"].to_numpy(), INK2),
              ("logístico p ≥ 0,5", A["pasa_logit"].to_numpy(), "#2a78d6")]
    x = np.arange(len(TRAMOS_BANDA) + 1)
    for k, (nombre, mask, color) in enumerate(series):
        ys, los, his, ns = [], [], [], []
        for t in [*TRAMOS_BANDA, "banda"]:
            g = mask & ((A["tramo"] == t).to_numpy() if t != "banda" else True)
            n, s = int(g.sum()), int(A["acierto"].to_numpy()[g].sum())
            lo, hi = wilson_interval(s, n) if n else (np.nan, np.nan)
            ys.append(s / n if n else np.nan)
            los.append(lo)
            his.append(hi)
            ns.append(n)
        xx = x + (k - 1) * 0.24
        ys, los, his = np.array(ys), np.array(los), np.array(his)
        ax.errorbar(xx, 100 * ys, yerr=[100 * (ys - los), 100 * (his - ys)], fmt="o", color=color, ms=8,
                    mec=SURFACE, mew=1.5, elinewidth=1.4, label=nombre)
        for xi, n in zip(xx, ns):
            ax.text(xi, 2, f"n={n}", ha="center", fontsize=7, color=MUTED)
    ax.axhline(81, color=AXIS, lw=1, ls="--")
    ax.text(x[-1] + 0.45, 81, "≥ 0,80:\n81 %", va="center", ha="left", fontsize=8, color=INK2)
    ax.axvline(x[-1] - 0.5, color=AXIS, lw=0.8)
    ax.set_xticks(x, [t.replace(".", ",") for t in TRAMOS_BANDA] + ["toda la banda"])
    ax.set_xlim(-0.5, x[-1] + 0.9)
    ax.set_ylim(0, 105)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f} %"))
    ax.set_ylabel("anotadas «mismo hecho» entre las que pasan")
    ax.set_title("Precisión medida con las parejas anotadas (IC 95 % Wilson)", fontsize=10)
    ax.grid(axis="x", visible=False)
    ax = axes[1]
    yb = np.arange(len(TRAMOS_BANDA))
    tot = pob.groupby("tramo").size().reindex(TRAMOS_BANDA)
    fil = pob[pob["variante"] == "filtrada"].groupby("tramo").size().reindex(TRAMOS_BANDA)
    ax.barh(yb, tot, color="#e1e0d9", height=0.6, label="banda (todas)")
    ax.barh(yb, fil, color=INK2, height=0.6, label="pasan la regla")
    for y, t, f in zip(yb, tot, fil):
        ax.text(t, y, f"  {miles(f)} de {miles(t)} ({100 * f / t:.0f} %)", va="center", fontsize=8, color=INK2)
    ax.set_yticks(yb, [t.replace(".", ",") for t in TRAMOS_BANDA])
    ax.invert_yaxis()
    ax.set_xlim(0, tot.max() * 1.6)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: miles(v)))
    ax.set_xlabel("parejas recíprocas en el corpus")
    ax.set_title("Cuántas parejas quedan", fontsize=10)
    ax.grid(axis="y", visible=False)
    handles = [Line2D([], [], marker="o", ls="", color=c, ms=8, label=n) for n, _, c in series]
    fig.tight_layout(w_pad=3)
    _margins(fig, handles, ncol=3, top_in=0.9, bottom_in=0.8)
    _save(fig, res, "33_filtro_banda.png", "¿Cuántas parejas de la banda 0,65–0,80 son el mismo hecho?",
          f"Regla: {regla_txt}. Elegida en una rejilla de {len(reglas())} reglas por la cota inferior de Wilson; su "
          f"precisión fuera de la muestra (validación cruzada anidada, {anidada['repeticiones']} repeticiones) es "
          f"{100 * anidada['precision_mediana']:.0f} % (percentiles 2,5–97,5: {100 * anidada['p2_5']:.0f}–"
          f"{100 * anidada['p97_5']:.0f} %). Logístico: similitud, días, términos raros; validación cruzada sobre las "
          f"{miles(prec['anotadas_total'].iat[0])} parejas anotadas de todos los tramos. "
          f"Línea punteada: precisión ponderada de los eventos ≥ 0,80. {NOTA_BANDA} {FUENTE}")


MARCA = {"formato": " [formato]", "atribucion": " [atrib.]", "contenido": ""}


def fig_distintivas(lo, rcn_desde, res, n=10):
    fig, axes = plt.subplots(len(MEDIA), 2, figsize=(12, 17))
    xmax = 0
    for i, m in enumerate(MEDIA):
        for j, g in enumerate(GOVS):
            ax = axes[i, j]
            t = lo[(lo["medio"] == m) & (lo["gobierno"] == g) & lo["distintiva"] & (lo["clase"] != "formato")]
            t = t.sort_values("z", ascending=False)
            # las nuevas suelen tener z menor que las de siempre: se reservan hasta 4 filas para ellas
            nuevas = t[t["nueva_estricta"]].head(4)
            t = pd.concat([nuevas, t[~t["nueva_estricta"]].head(n - len(nuevas))])
            t = t.sort_values("z", ascending=False).iloc[::-1]
            y = np.arange(len(t))
            for yy, r in zip(y, t.itertuples()):
                color = GOV_COLORS[g] if r.clase == "contenido" else "#b8b6ad"
                ax.barh(yy, r.delta, color=color if r.nueva_estricta else SURFACE, edgecolor=color,
                        alpha=1.0 if r.robusta else 0.45, height=0.62, linewidth=1.6)
                ax.plot([r.ic_bajo, r.ic_alto], [yy, yy], color=INK2, lw=1)
            ax.set_yticks(y, [f"{r.termino}{MARCA[r.clase]}{' *' if r.tambien_en_rechazadas else ''}"
                              for r in t.itertuples()], fontsize=8.5)
            xmax = max(xmax, t["ic_alto"].max() if len(t) else 0)
            celda = lo[(lo["medio"] == m) & (lo["gobierno"] == g)]
            sub = f"{MEDIA_NAMES[m]} · {GOV_NAMES[g]} · {miles(celda['parejas'].iat[0]) if len(celda) else '—'} parejas"
            if m == RCN and g == "duque":
                sub += f" (desde {rcn_desde:%Y-%m})"
            ax.set_title(sub, fontsize=10)
            ax.grid(axis="y", visible=False)
            ax.axvline(0, color=AXIS, lw=0.8)
            ax.set_ylim(len(t) - n - 0.4, len(t) - 0.4)
            if not len(t):
                ax.text(0.5, 0.5, "sin palabras significativas", transform=ax.transAxes, ha="center", color=MUTED)
    for ax in axes.ravel():
        ax.set_xlim(0, xmax * 1.05)
    for ax in axes[-1]:
        ax.set_xlabel("log-odds vs. el otro medio de la pareja (IC 95 %)")
    handles = [plt.Rectangle((0, 0), 1, 1, color=GOV_COLORS["duque"], label="nueva (no significativa con ≥ 0,80), Duque"),
               plt.Rectangle((0, 0), 1, 1, color=GOV_COLORS["petro"], label="nueva, Petro"),
               plt.Rectangle((0, 0), 1, 1, facecolor=SURFACE, edgecolor=INK2, lw=1.6, label="ya significativa con ≥ 0,80"),
               plt.Rectangle((0, 0), 1, 1, color="#b8b6ad", label="verbo de atribución"),
               plt.Rectangle((0, 0), 1, 1, color=MUTED, alpha=0.45, label="no robusta")]
    fig.tight_layout(h_pad=1.6, w_pad=3)
    _margins(fig, handles, ncol=3, top_in=1.1, bottom_in=0.6)
    _save(fig, res, "34_palabras_banda.png", "Palabras propias de cada medio en la banda 0,65–0,80 (filtrada)",
          "Hasta diez términos distintivos (bootstrap por parejas, FDR q < 0,05, ≥10 parejas y ≥5 en que sólo el medio "
          "lo usa) por medio y gobierno, en las parejas que pasan el filtro; sin términos de formato. Relleno: en los "
          "eventos ≥ 0,80 no era significativa (z < 1,96); contorno: ya lo era. Robusta = además z ≥ 1,96 con bootstrap por meses y "
          "sin RCN como contraparte. * = también separa al medio en las parejas que el filtro rechaza (mayoría de "
          f"hechos distintos): más rasgo de la casa o de agenda que encuadre. RCN en Duque sólo desde {rcn_desde:%Y-%m}. "
          f"Precisión del filtro ≈ 70–80 %: resultado exploratorio. {NOTA_BANDA} {FUENTE}", note_y=0.0)


def fig_personalizacion(par080: pd.DataFrame, parb: pd.DataFrame, rcn_desde, res, prec_txt: str):
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.4), sharey=True)
    x = np.arange(len(MEDIA))
    conjuntos = [("≥ 0,80 (eventos)", par080, "o", True), ("banda filtrada", parb[parb["variante"] == "filtrada"],
                                                            "s", True),
                 ("banda sin filtro", parb[parb["variante"] == "sin_filtro"], "D", False)]
    for ax, g in zip(axes, GOVS):
        for k, (nombre, t, mk, lleno) in enumerate(conjuntos):
            t = t[(t["forma"] == "pers_gobierno") & (t["gobierno"] == g) & (t["otros"] == "todos")]
            t = t.set_index("medio").reindex(MEDIA)
            xx = x + (k - 1) * 0.24
            ax.errorbar(xx, 100 * t["diferencia"], yerr=[100 * (t["diferencia"] - t["ic_bajo"]),
                                                         100 * (t["ic_alto"] - t["diferencia"])],
                        fmt=mk, color=GOV_COLORS[g], mfc=GOV_COLORS[g] if lleno else SURFACE, ms=7,
                        mec=GOV_COLORS[g], mew=1.5, elinewidth=1.2, alpha=1.0 if k < 2 else 0.7)
        ax.axhline(0, color=INK2, lw=0.8)
        ax.set_xticks(x, [SHORT[m] for m in MEDIA])
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:+.0f} pp"))
        sub = f"Gobierno {GOV_NAMES[g]}" + (f" (RCN desde {rcn_desde:%Y-%m})" if g == "duque" else "")
        ax.set_title(sub, fontsize=10)
        ax.grid(axis="x", visible=False)
    axes[0].set_ylabel("personalización del medio − la del otro medio")
    handles = [Line2D([], [], marker=mk, ls="", mfc=INK2 if lleno else SURFACE, mec=INK2, color=INK2, ms=8, label=n)
               for n, _, mk, lleno in conjuntos]
    fig.tight_layout(w_pad=3)
    _margins(fig, handles, ncol=3, top_in=0.9, bottom_in=0.8)
    _save(fig, res, "35_personalizacion_banda.png", "¿Se mantiene «Gobierno Petro» frente a «el Gobierno» en la banda?",
          "Índice de personalización del gobierno («Gobierno + apellido» entre los titulares que dicen «Gobierno "
          "Petro/Duque», «Gobierno nacional» o «Gobierno» sin más) del medio menos el de los otros medios en los "
          "mismos eventos (≥ 0,80, lexico.py) o el del otro medio de la pareja (banda), en eventos o parejas "
          "domésticas; cociente de sumas, IC 95 % por bootstrap de eventos o parejas. "
          f"{prec_txt} {NOTA_BANDA} {FUENTE}")


# ── etapa principal ──────────────────────────────────────────────────────────


def _r(x, k=4):
    return None if x is None or (isinstance(x, float) and not np.isfinite(x)) else round(float(x), k)


def anotaciones(frame: pd.DataFrame, out: Path) -> pd.DataFrame:
    """Parejas anotadas de la calibración con su índice en `frame` y la etiqueta
    (Anotador 1, como calibracion.py; «No se puede saber» fuera)."""
    cal = out / "calibracion"
    key = pd.read_csv(cal / "clave_no_abrir.csv")
    ann = combine_personas([pd.read_excel(cal / f"planilla_persona_{k}.xlsx", sheet_name="Anotación")
                            for k in (1, 2)])
    A = ann.merge(key, on="pareja", validate="one_to_one")
    A = A.rename(columns={"Anotador 1 · ¿mismo hecho?": "etiqueta"})
    A = A[A["etiqueta"].isin(ETIQUETAS[:3])].copy()
    pos = pd.Series(np.arange(len(frame)), index=frame["article_id"])
    A["i"], A["j"] = pos.reindex(A["article_id_a"]).to_numpy(), pos.reindex(A["article_id_b"]).to_numpy()
    A = A.dropna(subset=["i", "j"])
    A["i"], A["j"] = A["i"].astype(int), A["j"].astype(int)
    A["acierto"] = A["etiqueta"].eq(POSITIVA)
    return A.reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, default=HERE / "resultados_publico")
    parser.add_argument("--reps", type=int, default=2000, help="Réplicas del bootstrap de log-odds (principal)")
    parser.add_argument("--reps-variantes", type=int, default=500, help="Réplicas en robustez y variantes")
    parser.add_argument("--reps-formas", type=int, default=2000)
    parser.add_argument("--reps-anidada", type=int, default=200, help="Repeticiones de la validación anidada")
    parser.add_argument("--alpha0", type=float, default=100.0)
    parser.add_argument("--min-eventos", type=int, default=10, help="Parejas mínimas con el término")
    parser.add_argument("--min-discordantes", type=int, default=5)
    parser.add_argument("--rcn-min-dia", type=float, default=0.75)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    out = args.output.resolve()
    res = out / "lexico_banda"
    (res / "figuras").mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()

    _, rcn_desde = precision_fecha_rcn(out, args.rcn_min_dia)
    frame, _, day, media, info = eventos._load(out)
    mej = np.load(out / "eventos" / "mejores.npz")
    pi, pj, ps = eventos.reciprocal_pairs(mej["best_idx"], mej["best_sim"], media)
    ev = pd.read_parquet(out / "eventos" / "eventos.parquet", columns=["event_id", "article_id"])
    ev_de = evento_de_titular(frame, ev)
    topic = frame["topic"].to_numpy()
    stop = stop_lexico()
    uni = [set(tokenize(t, stop)) for t in frame["title"]]
    idf = idf_titulares(uni)
    logging.info("%s titulares, %s parejas recíprocas", len(frame), len(pi))

    # ── población de la banda y rasgos
    P = parejas_banda(pi, pj, ps, ev_de)
    P["pareja"] = np.arange(len(P))
    P["tramo"] = P["sim"].map(tramo)
    R = tabla_rasgos(P, uni, idf, day, topic)
    n_banda_total = int(((ps >= BANDA[0]) & (ps < BANDA[1])).sum())
    logging.info("Banda: %s parejas (%s ya en un mismo evento ≥ 0,80)", len(P), n_banda_total - len(P))

    # ── anotaciones y filtro
    A = anotaciones(frame, out)
    Ra = tabla_rasgos(A.rename(columns={"similitud": "sim"}), uni, idf, day, topic)
    A["dias"] = Ra["dias"].to_numpy()
    A["en_mismo_evento"] = (ev_de[A["i"]] >= 0) & (ev_de[A["i"]] == ev_de[A["j"]])
    banda_a = ((A["similitud"] >= BANDA[0]) & (A["similitud"] < BANDA[1]) & ~A["en_mismo_evento"]).to_numpy()
    Ab, Rb = A[banda_a].reset_index(drop=True), Ra[banda_a].reset_index(drop=True)
    yb = Ab["acierto"].to_numpy()
    todas = reglas()
    k_regla = elegir_regla(Rb, yb, todas)
    regla = todas[k_regla]
    regla_txt = describe_regla(regla)
    rejilla = []
    for k, r in enumerate(todas):
        m = aplica_regla(Rb, r)
        n, s = int(m.sum()), int(yb[m].sum())
        lo, hi = wilson_interval(s, n) if n else (np.nan, np.nan)
        rejilla.append({**r, "regla": describe_regla(r), "pasan": n, "mismo_hecho": s,
                        "precision": s / n if n else np.nan, "ic_bajo": lo, "ic_alto": hi, "elegida": k == k_regla})
    rejilla = pd.DataFrame(rejilla).sort_values("ic_bajo", ascending=False)
    rejilla.to_csv(res / "filtro_rejilla.csv", index=False)
    anidada = precision_anidada(Rb, yb, todas, reps=args.reps_anidada, seed=args.seed)
    p_oof, logit = logistica_oof(Ra, A["acierto"].to_numpy(), seed=args.seed)
    Ab["pasa"] = aplica_regla(Rb, regla)
    Ab["p_logit"] = p_oof[banda_a]
    Ab["pasa_logit"] = Ab["p_logit"] >= 0.5
    Ab["pasa_propuesta"] = aplica_regla(Rb, {"dias_max": 1, "df_raro": 1000, "n_raro_min": 1, "mismo_topico": True})
    from sklearn.metrics import roc_auc_score
    auc = {c: float(roc_auc_score(yb, Rb[c])) for c in ["sim", "dias", "sum_idf", "wjac", "n_raro_1000",
                                                         "mismo_topico"]}
    auc["logistico_oof"] = float(roc_auc_score(yb, Ab["p_logit"]))
    coefs = dict(zip(RASGOS_LOGIT, logit[-1].coef_[0].round(3).tolist()))

    # población: qué pasa cada filtro
    P["logit"] = logit.predict_proba(R[RASGOS_LOGIT].to_numpy(float))[:, 1]
    pasa_pob = aplica_regla(R, regla)
    P["variante"] = np.where(pasa_pob, "filtrada", "rechazada")
    R["variante"], R["pareja"], R["tramo"] = P["variante"].to_numpy(), P["pareja"].to_numpy(), P["tramo"].to_numpy()
    pob = {"sin filtro": P.groupby("tramo").size(), "regla": P[pasa_pob].groupby("tramo").size(),
           "logístico": P[P["logit"] >= 0.5].groupby("tramo").size(),
           "regla propuesta (a priori)": P[aplica_regla(R, {"dias_max": 1, "df_raro": 1000, "n_raro_min": 1,
                                                          "mismo_topico": True})].groupby("tramo").size()}
    prec = pd.DataFrame([
        precision_filtro("sin filtro", np.ones(len(Ab), bool), Ab, pob["sin filtro"]),
        precision_filtro("regla", Ab["pasa"].to_numpy(), Ab, pob["regla"]),
        precision_filtro("logístico", Ab["pasa_logit"].to_numpy(), Ab, pob["logístico"]),
        precision_filtro("regla propuesta (a priori)", Ab["pasa_propuesta"].to_numpy(), Ab,
                         pob["regla propuesta (a priori)"]),
    ])
    prec.insert(1, "descripcion", ["toda la banda", regla_txt, "logístico (sim, días, términos raros) p ≥ 0,5",
                                   "mismo tópico + ≤ 1 día + ≥ 1 término en ≤ 1.000 titulares"])
    prec["anotadas_total"] = len(A)
    prec.to_csv(res / "precision_filtro.csv", index=False)
    p_regla = prec[prec["filtro"] == "regla"].iloc[0]
    logging.info("Regla: %s → %s/%s (%.0f %%), anidada %.0f %%", regla_txt, p_regla["mismo_hecho"],
                 p_regla["pasan"], 100 * p_regla["precision"], 100 * anidada["precision_mediana"])
    Ab.assign(titular_a=frame["title"].to_numpy()[Ab["i"]], titular_b=frame["title"].to_numpy()[Ab["j"]]).drop(
        columns=[c for c in Ab.columns if c.startswith("Anotador")]).to_csv(res / "anotadas_banda.csv", index=False)

    # solapamiento léxico: ¿el filtro vuelve a seleccionar redacciones parecidas?
    alta = pd.DataFrame({"i": pi[ps >= 0.80], "j": pj[ps >= 0.80], "sim": ps[ps >= 0.80].astype(float)})
    R80 = tabla_rasgos(alta, uni, idf, day, topic)
    solap = pd.DataFrame([solapamiento(R80, "≥ 0,80 (parejas recíprocas)"), solapamiento(R, "banda sin filtro"),
                          solapamiento(R[pasa_pob], "banda filtrada"), solapamiento(R[~pasa_pob], "banda rechazada")])
    solap.to_csv(res / "solapamiento_lexico.csv", index=False)

    # ── tabla larga y matriz de términos (toda la banda)
    L = tabla_larga(P, frame)
    X, vocab, sets_l = matriz_terminos(L, stop, args.min_eventos)
    tasa = (np.asarray(X[L.drop_duplicates("fila").index].sum(axis=0)).ravel() + 0.5) / (L["fila"].nunique() + 1)
    prior = (args.alpha0 * tasa, args.alpha0)
    logging.info("Tabla larga: %s filas, %s términos", len(L), len(vocab))
    tam = L.groupby(["variante", "gobierno", "source_id"])["event_id"].nunique().rename("parejas").reset_index()
    tam.to_csv(res / "tamanos.csv", index=False)

    Lf = L[L["variante"] == "filtrada"]
    lo = log_odds_variante(Lf, X, vocab, prior, rcn_desde, args, robustez=True, sets=sets_l)
    logging.info("log-odds principal listo (%.0f s)", time.monotonic() - t0)
    otras = {"sin_filtro": log_odds_variante(L, X, vocab, prior, rcn_desde, args, robustez=False),
             "rechazada": log_odds_variante(L[L["variante"] == "rechazada"], X, vocab, prior, rcn_desde, args,
                                            robustez=False),
             "logistica": log_odds_variante(L[L["logit"] >= 0.5], X, vocab, prior, rcn_desde, args, robustez=False)}
    logging.info("log-odds variantes listos (%.0f s)", time.monotonic() - t0)
    lo80 = pd.read_csv(out / "lexico" / "logodds_medio_gobierno.csv")
    lo = comparar_con_080(lo, lo80, otras)
    lo.to_csv(res / "logodds_banda.csv", index=False)
    resumen = resumen_celdas(lo, lo80)
    resumen.to_csv(res / "resumen_celdas.csv", index=False)
    nuevas = lo[lo["nueva"] & (lo["clase"] == "contenido")].sort_values(["medio", "gobierno", "z"],
                                                                       ascending=[True, True, False])
    nuevas.to_csv(res / "palabras_nuevas.csv", index=False)

    # ── formas de nombrar
    F = matriz_formas(L)
    formas = pd.concat([formas_variante(L[L["variante"] == "filtrada"], F, rcn_desde, args, "filtrada"),
                        formas_variante(L, F, rcn_desde, args, "sin_filtro"),
                        formas_variante(L[L["logit"] >= 0.5], F, rcn_desde, args, "logistica")], ignore_index=True)
    formas.to_csv(res / "formas_nombrar_emparejado.csv", index=False)
    props, cambio = formas_props(Lf, F, rcn_desde)
    props.to_csv(res / "formas_nombrar.csv", index=False)
    cambio.to_csv(res / "formas_nombrar_cambio.csv", index=False)
    par080 = pd.read_csv(out / "lexico" / "formas_nombrar_emparejado.csv")
    comp = []
    for g in GOVS:
        for m in MEDIA:
            fila = {"medio": m, "gobierno": g}
            for etiqueta, t in (("080", par080.assign(variante="080")), ("filtrada", formas), ("sin_filtro", formas),
                                ("logistica", formas)):
                for otros in ("todos", "sin_rcn", "ventana_comun"):
                    r = t[(t["variante"] == etiqueta) & (t["medio"] == m) & (t["gobierno"] == g)
                          & (t["forma"] == "pers_gobierno") & (t["otros"] == otros)]
                    suf = etiqueta + {"todos": "", "sin_rcn": "_sinrcn", "ventana_comun": "_ventana"}[otros]
                    if len(r):
                        r = r.iloc[0]
                        fila.update({f"dif_{suf}": r.diferencia, f"ic_bajo_{suf}": r.ic_bajo,
                                     f"ic_alto_{suf}": r.ic_alto, f"n_ref_{suf}": r.get("n_ref_medio", np.nan)})
            comp.append(fila)
    comp = pd.DataFrame(comp)
    comp.to_csv(res / "personalizacion_comparada.csv", index=False)

    # ── ejemplos y figuras
    (res / "ejemplos_banda.md").write_text(
        ejemplos_md(L, sets_l, lo, F, R, Ab, frame, regla_txt, p_regla, args.seed), encoding="utf-8")
    fig_filtro(prec, Ab, P, res, regla_txt, anidada)
    fig_distintivas(lo, rcn_desde, res)
    prec_txt = (f"Precisión del filtro {100 * p_regla['precision']:.0f} % (IC 95 % {100 * p_regla['ic_bajo']:.0f}–"
                f"{100 * p_regla['ic_alto']:.0f} %); sin filtro ≈ "
                f"{100 * prec.loc[prec['filtro'] == 'sin filtro', 'precision'].iat[0]:.0f} %.")
    fig_personalizacion(par080, formas, rcn_desde, res, prec_txt)

    # ── cifras clave
    def top(m, g, n=10):
        t = lo[(lo["medio"] == m) & (lo["gobierno"] == g) & lo["distintiva"] & (lo["clase"] == "contenido")]
        return [f"{r.termino} ({r.delta:+.2f}; z {r.z:.1f}; {r.n_eventos_medio} par.; "
                f"{'nueva' if r.nueva_estricta else 'ya ≥0,80'}{'; robusta' if r.robusta else ''}"
                f"{'; también en rechazadas' if r.tambien_en_rechazadas else ''})"
                for r in t.sort_values("z", ascending=False).head(n).itertuples()]

    save_json(res / "lexico_banda.json", {
        "parametros": {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(args).items()},
        "banda": list(BANDA), "parejas_banda_total": n_banda_total, "parejas_banda_fuera_de_eventos": len(P),
        "parejas_por_variante": P["variante"].value_counts().to_dict(),
        "parejas_logistico": int((P["logit"] >= 0.5).sum()),
        "parejas_cruzan_gobierno_descartadas": int(len(P) - L["event_id"].nunique()),
        "rcn_desde": rcn_desde.strftime("%Y-%m"),
        "filtro": {"regla": regla, "descripcion": regla_txt, "rejilla_reglas": len(todas),
                   "criterio": "mayor cota inferior de Wilson de la precisión sobre las anotadas de la banda",
                   "anotadas_banda": int(len(Ab)), "anotadas_banda_mismo_hecho": int(yb.sum()),
                   "anotadas_banda_excluidas_por_estar_en_un_evento": int(((A["similitud"] >= BANDA[0])
                                                                           & (A["similitud"] < BANDA[1])
                                                                           & A["en_mismo_evento"]).sum()),
                   "precision": prec.round(4).to_dict(orient="records"),
                   "validacion_anidada": anidada, "auc_banda": auc, "coeficientes_logistico_estandarizados": coefs,
                   "exploratorio": bool(p_regla["precision"] < 0.70 or anidada["precision_mediana"] < 0.70
                                        or p_regla["ic_bajo"] < 0.70)},
        "solapamiento_lexico": solap.round(4).to_dict(orient="records"),
        "resumen_celdas": resumen.round(4).to_dict(orient="records"),
        "top_contenido": {m: {g: top(m, g) for g in GOVS} for m in MEDIA},
        "personalizacion_comparada": comp.round(4).to_dict(orient="records"),
        "cambio_formas": cambio.round(4).to_dict(orient="records"),
        "segundos": round(time.monotonic() - t0),
    })
    logging.info("Listo en %.0f s → %s", time.monotonic() - t0, res)


if __name__ == "__main__":
    main()
