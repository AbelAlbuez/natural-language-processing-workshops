"""Análisis del silver standard de titulares sesgados.

Corre después de `silver.py evaluar`. Lee las dos planillas, la clave y la
población por estrato, y responde:

1. ¿Qué tan seguido se juzga sesgado un titular, por medio, gobierno y medio ×
   gobierno? ¿Hacia dónde (favorable / desfavorable al gobierno de turno)?
2. ¿Sirven el léxico de carga (`lexico_carga.csv` de carga.py y la lista de
   candidatos de silver.py) y la personalización («Gobierno Petro/Duque») como
   indicadores de sesgo? Precisión y cobertura ponderadas.
3. ¿Se puede aprender la etiqueta con un clasificador simple? (prueba de concepto)

Las dos planillas no las anotaron dos personas: la 1 la anotó una persona del
equipo y la 2 un modelo de lenguaje («Claude (IA)»). Por eso todo se reporta por
anotador (`humano`, `ia`) y, como resumen, con las dos etiquetas combinadas
(`combinado_laxo`: un desacuerdo cuenta como «Sí»; `combinado_estricto`: como
«No»). La IA nunca dijo «Sí» donde la persona dijo «No»: es un umbral más
exigente, no ruido.

Pesos: cada titular vale N_h / n_h de su celda medio × gobierno × estrato,
con n_h contado dentro de la definición (cada anotador vio su propia submuestra).

Uso: python silver_analisis.py [--reps 2000]
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from core import normalize
from figuras import AXIS, GOV_COLORS, GOV_NAMES, INK2, MEDIA, MUTED, SHORT, SURFACE, _margins, _save
from silver import OUT, leer_planilla, tasa_ponderada

log = logging.getLogger("silver_analisis")
RES = OUT / "analisis"
DEFINICIONES = ["humano", "ia", "combinado_laxo", "combinado_estricto"]
NOMBRE_DEF = {"humano": "Persona", "ia": "IA (Claude)", "combinado_laxo": "Combinado laxo",
              "combinado_estricto": "Combinado estricto"}


# ── etiquetas ────────────────────────────────────────────────────────────────


def _bin(s: pd.Series) -> pd.Series:
    return s.map({"Sí": 1.0, "No": 0.0})  # «No se puede saber» y vacíos → NaN


def etiquetas(p1: pd.DataFrame, p2: pd.DataFrame, key: pd.DataFrame, muestra: pd.DataFrame) -> pd.DataFrame:
    """Formato largo: una fila por titular y definición, con y (0/1), tipo y dirección."""
    base = key.merge(muestra[["id", "titular", "gobierno"]], on="id")
    rows = []
    for nombre, p in (("humano", p1), ("ia", p2)):
        d = p.assign(y=_bin(p["¿sesgado?"]), tipo=p["tipo principal"], direccion=p["dirección"])
        rows.append(d[["id", "y", "tipo", "direccion"]].assign(definicion=nombre))
    a = p1.set_index("id")
    b = p2.set_index("id")
    ids = sorted(set(a.index) | set(b.index))
    for nombre, empate in (("combinado_laxo", 1.0), ("combinado_estricto", 0.0)):
        out = []
        for i in ids:
            ya = _bin(pd.Series([a.at[i, "¿sesgado?"]])).iloc[0] if i in a.index else np.nan
            yb = _bin(pd.Series([b.at[i, "¿sesgado?"]])).iloc[0] if i in b.index else np.nan
            vals = [v for v in (ya, yb) if not np.isnan(v)]
            y = np.nan if not vals else (vals[0] if len(set(vals)) == 1 else empate)
            # tipo y dirección: de quien dijo «Sí» (la persona si ambas)
            src = a if (i in a.index and ya == 1) else b
            pos = y == 1 and i in src.index
            out.append({"id": i, "y": y, "tipo": src.at[i, "tipo principal"] if pos else None,
                        "direccion": src.at[i, "dirección"] if pos else None})
        rows.append(pd.DataFrame(out).assign(definicion=nombre))
    lab = pd.concat(rows, ignore_index=True).merge(base, on="id")
    return lab


def pesos(d: pd.DataFrame, pe: pd.DataFrame) -> pd.Series:
    """w = N_h / n_h dentro de la definición (n_h: titulares útiles de esa celda × estrato)."""
    k = ["source_id", "government_id", "estrato"]
    n = d.groupby(k)["id"].transform("count")
    N = d[k].merge(pe, on=k, how="left")["N_h"].to_numpy()
    return pd.Series(N / n.to_numpy(), index=d.index)


# ── tasas ────────────────────────────────────────────────────────────────────


def _tasas(d: pd.DataFrame, pe: pd.DataFrame, col: str = "y") -> pd.DataFrame:
    x = d.assign(sesgado_bin=d[col])
    return pd.concat([tasa_ponderada(x, pe, ["source_id", "government_id"]),
                      tasa_ponderada(x, pe, ["source_id"]).assign(government_id="ambos"),
                      tasa_ponderada(x, pe, ["government_id"]).assign(source_id="todos")], ignore_index=True)


def _p(d: pd.DataFrame, w: np.ndarray, col: str) -> float:
    return float((w * d[col].to_numpy()).sum() / w.sum())


def boot_diferencias(d: pd.DataFrame, pe: pd.DataFrame, col: str, reps: int, seed: int) -> pd.DataFrame:
    """Petro − Duque de la tasa ponderada por medio (y todos), con bootstrap
    estratificado (remuestreo dentro de cada celda × estrato). También la
    diferencia relativa: la del medio menos la media de los otros cuatro."""
    rng = np.random.default_rng(seed)
    k = ["source_id", "government_id", "estrato"]
    grupos = [g.index.to_numpy() for _, g in d.groupby(k)]

    def est(dd):
        w = pesos(dd, pe).to_numpy()
        dd = dd.assign(_w=w, _yw=w * dd[col].to_numpy())
        s = dd.groupby(["source_id", "government_id"])[["_yw", "_w"]].sum()
        p = (s["_yw"] / s["_w"]).unstack()
        delta = (p["petro"] - p["duque"]).reindex(MEDIA)
        tot = dd.groupby("government_id")[["_yw", "_w"]].sum()
        pt = tot["_yw"] / tot["_w"]
        rel = {m: delta[m] - delta.drop(m).mean() for m in MEDIA}
        return np.r_[delta.to_numpy(), pt["petro"] - pt["duque"], [rel[m] for m in MEDIA]]

    obs = est(d)
    draws = np.empty((reps, len(obs)))
    for r in range(reps):
        idx = np.concatenate([rng.choice(g, len(g), replace=True) for g in grupos])
        draws[r] = est(d.loc[idx].reset_index(drop=True))
    nombres = [(m, "delta") for m in MEDIA] + [("todos", "delta")] + [(m, "delta_relativo") for m in MEDIA]
    rows = []
    for j, (m, tipo) in enumerate(nombres):
        lo, hi = np.nanpercentile(draws[:, j], [2.5, 97.5])
        p = 2 * min((draws[:, j] <= 0).mean(), (draws[:, j] >= 0).mean())
        rows.append({"source_id": m, "medida": tipo, "valor": obs[j], "ic_bajo": lo, "ic_alto": hi,
                     "p_boot": min(1.0, p)})
    return pd.DataFrame(rows)


# ── validación de indicadores ────────────────────────────────────────────────


def prec_cob(d: pd.DataFrame, pe: pd.DataFrame, x: pd.Series, reps: int, seed: int) -> dict:
    """Precisión P(sesgado | indicador) y cobertura P(indicador | sesgado), ponderadas,
    con bootstrap estratificado."""
    k = ["source_id", "government_id", "estrato"]
    d = d.assign(_x=x.astype(float).to_numpy())

    def est(dd):
        w = pesos(dd, pe).to_numpy()
        y, xx = dd["y"].to_numpy(), dd["_x"].to_numpy()
        tp = (w * y * xx).sum()
        return (tp / (w * xx).sum() if (w * xx).sum() else np.nan,
                tp / (w * y).sum() if (w * y).sum() else np.nan,
                (w * y).sum() / w.sum(), (w * xx).sum() / w.sum())

    obs = est(d)
    rng = np.random.default_rng(seed)
    grupos = [g.index.to_numpy() for _, g in d.groupby(k)]
    draws = np.array([est(d.loc[np.concatenate([rng.choice(g, len(g)) for g in grupos])].reset_index(drop=True))
                      for _ in range(reps)])
    ci = np.nanpercentile(draws, [2.5, 97.5], axis=0)
    return {"n": int(len(d)), "n_indicador": int(d["_x"].sum()), "positivos_con_indicador": int((d["_x"] * d["y"]).sum()),
            "precision": obs[0], "precision_ic": list(ci[:, 0]), "cobertura": obs[1], "cobertura_ic": list(ci[:, 1]),
            "prevalencia": obs[2], "frecuencia_indicador": obs[3],
            "lift": obs[0] / obs[2] if obs[2] else np.nan}


def indicadores(lab: pd.DataFrame) -> pd.DataFrame:
    """Indicadores binarios por titular: lista de candidatos de silver.py, léxico de
    carga.py (negativa, positiva, cualquier carga, atribución cargada) y personalización."""
    import carga

    lex = carga.compilar(carga.leer_lexico())
    tit = lab.drop_duplicates("id").set_index("id")["titular"]
    E = carga.matriz_entradas([normalize(t) for t in tit], lex)
    E.index = tit.index
    I = carga.indicadores(E.reset_index(drop=True), lex)
    I.index = tit.index
    out = pd.DataFrame(index=tit.index)
    tc = lab.drop_duplicates("id").set_index("id")["terminos_carga"]
    out["candidatos_silver"] = tc.fillna("").astype(str).str.len().gt(0)
    for c in ("negativa", "positiva", "carga", "atrib_cargada"):
        out[f"carga_{c}"] = I[c].astype(float).ne(0) if c != "negativa" else I[c].astype(bool)
    out["personaliza"] = lab.drop_duplicates("id").set_index("id")["personaliza"].astype(bool)
    out["divergente"] = lab.drop_duplicates("id").set_index("id")["divergente"].astype(bool)
    return out, E


def por_entrada(lab: pd.DataFrame, E: pd.DataFrame, defin: str, min_n: int = 3) -> pd.DataFrame:
    d = lab[(lab.definicion == defin) & lab.y.notna()].set_index("id")
    rows = []
    for c in E.columns:
        m = E.loc[d.index, c]
        if m.sum() >= min_n:
            g = d[m.to_numpy()]
            rows.append({"entrada": c, "definicion": defin, "titulares": int(len(g)), "sesgados": int(g.y.sum()),
                         "tasa": g.y.mean(), "ejemplo_no_sesgado": next(iter(g.loc[g.y == 0, "titular"]), "")})
    return pd.DataFrame(rows).sort_values(["titulares"], ascending=False) if rows else pd.DataFrame()


# ── clasificador ─────────────────────────────────────────────────────────────


def clasificador(lab: pd.DataFrame, defin: str, seed: int = 42, folds: int = 5, repeats: int = 10) -> dict:
    """TF-IDF (palabras 1–2 + caracteres 3–5) + regresión logística, validación
    cruzada estratificada repetida. AUC comparada con la de un indicador del léxico."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import average_precision_score, roc_auc_score
    from sklearn.model_selection import RepeatedStratifiedKFold
    from sklearn.pipeline import make_pipeline, make_union

    d = lab[(lab.definicion == defin) & lab.y.notna()].reset_index(drop=True)
    X, y = d["titular"].map(normalize).to_numpy(), d["y"].astype(int).to_numpy()
    if y.sum() < 15 or (1 - y).sum() < 15:
        return {"definicion": defin, "n": int(len(y)), "positivos": int(y.sum()), "nota": "pocos positivos"}
    cv = RepeatedStratifiedKFold(n_splits=folds, n_repeats=repeats, random_state=seed)
    auc, ap, auc_lex = [], [], []
    lexf = d["_lex"].to_numpy().astype(float)
    for tr, te in cv.split(X, y):
        pipe = make_pipeline(make_union(TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True),
                                        TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2,
                                                        sublinear_tf=True)),
                             LogisticRegression(C=1.0, class_weight="balanced", max_iter=2000))
        pipe.fit(X[tr], y[tr])
        s = pipe.predict_proba(X[te])[:, 1]
        auc.append(roc_auc_score(y[te], s))
        ap.append(average_precision_score(y[te], s))
        auc_lex.append(roc_auc_score(y[te], lexf[te]))
    # palabras con más peso (modelo con todos los datos, sólo como descripción)
    vec = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True)
    Xw = vec.fit_transform(X)
    lr = LogisticRegression(C=1.0, class_weight="balanced", max_iter=2000).fit(Xw, y)
    voc = np.array(vec.get_feature_names_out())
    o = np.argsort(lr.coef_[0])
    return {"definicion": defin, "n": int(len(y)), "positivos": int(y.sum()),
            "auc_media": float(np.mean(auc)), "auc_sd": float(np.std(auc)),
            "ap_media": float(np.mean(ap)), "prevalencia": float(y.mean()),
            "auc_lexico_carga": float(np.mean(auc_lex)),
            "palabras_sesgado": voc[o[::-1][:15]].tolist(), "palabras_no_sesgado": voc[o[:15]].tolist()}


# ── figuras ──────────────────────────────────────────────────────────────────


def _pct(v):
    return f"{100 * v:.0f} %"


def fig_tasas(t: pd.DataFrame, out: Path) -> None:
    defs = ["humano", "ia"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6), sharey=True)
    for ax, df in zip(axes, defs):
        tt = t[(t.definicion == df) & t.government_id.isin(["duque", "petro"])]
        for j, g in enumerate(["duque", "petro"]):
            s = tt[tt.government_id == g].set_index("source_id").reindex(MEDIA + ["todos"])
            ypos = np.arange(len(s)) + (j - 0.5) * 0.28
            ax.errorbar(100 * s.tasa_ponderada, ypos, xerr=[100 * (s.tasa_ponderada - s.ic_bajo).clip(lower=0),
                                                            100 * (s.ic_alto - s.tasa_ponderada).clip(lower=0)],
                        fmt="o", color=GOV_COLORS[g], ms=6, elinewidth=1.2, capsize=0)
        ax.set_yticks(range(len(MEDIA) + 1), [SHORT[m] for m in MEDIA] + ["Todos"])
        ax.invert_yaxis()
        ax.set_title(f"Etiquetas de: {NOMBRE_DEF[df]}", loc="left", fontsize=11, color=INK2)
        ax.set_xlabel("titulares juzgados sesgados (%, ponderado)")
        ax.set_xlim(0, 80)
        ax.grid(axis="x", color=AXIS, lw=0.5, alpha=0.6)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
    h = [plt.Line2D([], [], marker="o", ls="", color=GOV_COLORS[g], label=GOV_NAMES[g]) for g in GOV_COLORS]
    _margins(fig, h, ncol=2, top_in=1.0, bottom_in=0.9)
    _save(fig, out, "36_silver_tasa_sesgo.png",
          "La persona marca sesgo 2–3 veces más que la IA; entre medios los intervalos se solapan",
          "Silver standard: 300 titulares de asuntos públicos (180 por anotador), muestra estratificada por medio × "
          "gobierno × estrato, ponderada a la población (290.464 titulares). IC 95 % Wilson con n efectivo de Kish. "
          "RCN-Duque desde 2020-09.")


def fig_direccion(t: pd.DataFrame, out: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6), sharey=True)
    for ax, df in zip(axes, ["humano", "ia"]):
        tt = t[(t.definicion == df) & t.government_id.isin(["duque", "petro"])]
        for j, g in enumerate(["duque", "petro"]):
            s = tt[tt.government_id == g].set_index("source_id").reindex(MEDIA + ["todos"])
            ypos = np.arange(len(s)) + (j - 0.5) * 0.28
            ax.errorbar(100 * s.tasa_ponderada, ypos, xerr=[100 * (s.tasa_ponderada - s.ic_bajo).clip(lower=0),
                                                            100 * (s.ic_alto - s.tasa_ponderada).clip(lower=0)],
                        fmt="o", color=GOV_COLORS[g], ms=6, elinewidth=1.2, capsize=0)
        ax.set_yticks(range(len(MEDIA) + 1), [SHORT[m] for m in MEDIA] + ["Todos"])
        ax.invert_yaxis()
        ax.set_title(f"Etiquetas de: {NOMBRE_DEF[df]}", loc="left", fontsize=11, color=INK2)
        ax.set_xlabel("sesgo desfavorable al gobierno (%, ponderado)")
        ax.set_xlim(0, 80)
        ax.grid(axis="x", color=AXIS, lw=0.5, alpha=0.6)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
    h = [plt.Line2D([], [], marker="o", ls="", color=GOV_COLORS[g], label=GOV_NAMES[g]) for g in GOV_COLORS]
    _margins(fig, h, ncol=2, top_in=1.0, bottom_in=0.9)
    _save(fig, out, "37_silver_desfavorable.png",
          "Con los IC actuales, el sesgo desfavorable al gobierno no distingue medios ni gobiernos",
          "Proporción de todos los titulares (no sólo de los sesgados) con sesgo «Desfavorable» al gobierno de turno. "
          "Misma muestra y ponderación que la figura 36.")


def fig_validacion(v: pd.DataFrame, out: Path) -> None:
    orden = ["candidatos_silver", "carga_carga", "carga_negativa", "carga_positiva", "carga_atrib_cargada",
             "personaliza", "divergente"]
    nombres = {"candidatos_silver": "lista de candidatos (silver.py)", "carga_carga": "léxico carga.py: cualquiera",
               "carga_negativa": "léxico carga.py: negativa", "carga_positiva": "léxico carga.py: positiva",
               "carga_atrib_cargada": "verbo de atribución cargado", "personaliza": "«Gobierno Petro/Duque»",
               "divergente": "titular divergente del evento"}
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4), sharey=True)
    for ax, met in zip(axes, ["precision", "cobertura"]):
        for j, df in enumerate(["humano", "ia"]):
            s = v[v.definicion == df].set_index("indicador").reindex(orden)
            ypos = np.arange(len(s)) + (j - 0.5) * 0.28
            lo = s[f"{met}_ic"].map(lambda x: x[0])
            hi = s[f"{met}_ic"].map(lambda x: x[1])
            ax.errorbar(100 * s[met], ypos, xerr=[100 * (s[met] - lo).clip(lower=0), 100 * (hi - s[met]).clip(lower=0)], fmt="os"[j],
                        color=["#2a78d6", "#e34948"][j], mfc=["#2a78d6", SURFACE][j], ms=6, elinewidth=1.1)
            if met == "precision":
                ax.axvline(100 * s["prevalencia"].iloc[0], color=["#2a78d6", "#e34948"][j], lw=0.8, ls=":")
        ax.set_yticks(range(len(orden)), [nombres[o] for o in orden])
        ax.invert_yaxis()
        ax.set_xlim(0, 100)
        ax.set_title({"precision": "Precisión: de los que tienen el indicador, % sesgados",
                      "cobertura": "Cobertura: de los sesgados, % con el indicador"}[met],
                     loc="left", fontsize=10.5, color=INK2)
        ax.grid(axis="x", color=AXIS, lw=0.5, alpha=0.6)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
    h = [plt.Line2D([], [], marker="o", ls="", color="#2a78d6", label="etiquetas de la persona"),
         plt.Line2D([], [], marker="s", ls="", color="#e34948", mfc=SURFACE, label="etiquetas de la IA"),
         plt.Line2D([], [], ls=":", color=MUTED, label="prevalencia (línea punteada)")]
    _margins(fig, h, ncol=3, top_in=1.0, bottom_in=0.9)
    _save(fig, out, "38_silver_validacion_indicadores.png",
          "El léxico de carga enriquece la muestra, pero cubre menos del 15 % de los titulares sesgados",
          "Precisión y cobertura ponderadas a la población con IC 95 % por bootstrap estratificado. "
          "La línea punteada es la prevalencia: un indicador útil debe quedar a su derecha en precisión.")


# ── main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reps", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    (RES / "figuras").mkdir(parents=True, exist_ok=True)

    p1 = leer_planilla(OUT / "planilla_silver_persona_1.xlsx")
    p2 = leer_planilla(OUT / "planilla_silver_persona_2.xlsx")
    key = pd.read_csv(OUT / "clave_no_abrir.csv")
    muestra = pd.read_csv(OUT / "muestra.csv", keep_default_na=False)
    pe = pd.read_csv(OUT / "poblacion_estratos.csv")
    lab = etiquetas(p1, p2, key, muestra)
    I, E = indicadores(lab)
    lab = lab.drop(columns=["personaliza", "divergente"]).merge(I, left_on="id", right_index=True)
    lab["_lex"] = lab["carga_carga"]
    lab.drop(columns=["_lex"]).to_csv(RES / "etiquetas_por_definicion.csv", index=False)
    res = {"anotadores": {"planilla_1": p1["nombre"].dropna().unique().tolist(),
                          "planilla_2": p2["nombre"].dropna().unique().tolist()}}

    # Acuerdo en dobles: tabla cruzada
    dd = p1[p1.doble == "Sí"].merge(p2[p2.doble == "Sí"], on="id", suffixes=("_1", "_2"))
    res["dobles_tabla"] = pd.crosstab(dd["¿sesgado?_1"], dd["¿sesgado?_2"]).to_dict()
    res["si_ia_y_no_persona"] = int(((dd["¿sesgado?_2"] == "Sí") & (dd["¿sesgado?_1"] == "No")).sum())

    tasas, desf, fav, difs, vals, est, clf, ent = [], [], [], [], [], [], [], []
    for df in DEFINICIONES:
        d = lab[(lab.definicion == df) & lab.y.notna()].reset_index(drop=True)
        d["desf"] = ((d.y == 1) & (d.direccion == "Desfavorable")).astype(float)
        d["fav"] = ((d.y == 1) & (d.direccion == "Favorable")).astype(float)
        tasas.append(_tasas(d, pe).assign(definicion=df))
        desf.append(_tasas(d, pe, "desf").assign(definicion=df))
        fav.append(_tasas(d, pe, "fav").assign(definicion=df))
        for col in ("y", "desf"):
            difs.append(boot_diferencias(d, pe, col, args.reps, args.seed).assign(definicion=df, variable=col))
        for ind in I.columns:
            r = prec_cob(d, pe, d[ind], max(200, args.reps // 4), args.seed)
            vals.append({"definicion": df, "indicador": ind, **r})
        for h, g in d.groupby("estrato"):
            est.append({"definicion": df, "estrato": h, "n": len(g), "sesgados": int(g.y.sum()), "tasa": g.y.mean()})
        w = pesos(d, pe)
        tipos = (d.assign(w=w)[d.y == 1].groupby(["government_id", "tipo"])["w"].sum()
                 / d.assign(w=w)[d.y == 1].groupby("government_id")["w"].sum())
        res.setdefault("tipos_ponderados", {})[df] = {f"{g}|{t}": float(v) for (g, t), v in tipos.items()}
        dirs = (d.assign(w=w)[d.y == 1].groupby(["government_id", "direccion"])["w"].sum()
                / d.assign(w=w)[d.y == 1].groupby("government_id")["w"].sum())
        res.setdefault("direccion_entre_sesgados", {})[df] = {f"{g}|{t}": float(v) for (g, t), v in dirs.items()}
        if df in ("humano", "ia", "combinado_laxo"):
            clf.append(clasificador(lab, df, args.seed))
            ent.append(por_entrada(lab, E, df))
        log.info("Definición %s lista", df)

    T = pd.concat(tasas, ignore_index=True)
    T.to_csv(RES / "tasas_por_definicion.csv", index=False)
    D = pd.concat(desf, ignore_index=True)
    D.to_csv(RES / "tasas_desfavorable.csv", index=False)
    pd.concat(fav, ignore_index=True).to_csv(RES / "tasas_favorable.csv", index=False)
    pd.concat(difs, ignore_index=True).to_csv(RES / "diferencias_petro_duque.csv", index=False)
    V = pd.DataFrame(vals)
    V.to_csv(RES / "validacion_indicadores.csv", index=False)
    pd.DataFrame(est).to_csv(RES / "tasa_por_estrato.csv", index=False)
    pd.concat(ent, ignore_index=True).to_csv(RES / "entradas_lexico_vs_etiqueta.csv", index=False)
    res["clasificador"] = clf
    # tipos de los sesgados por anotador (sin ponderar)
    res["tipos_sin_ponderar"] = {k: p["tipo principal"].value_counts().to_dict() for k, p in (("humano", p1), ("ia", p2))}
    json.dump(res, open(RES / "silver_analisis.json", "w"), ensure_ascii=False, indent=2, default=float)

    fig_tasas(T, RES)
    fig_direccion(D, RES)
    fig_validacion(V, RES)
    log.info("Listo: %s", RES)


if __name__ == "__main__":
    main()
