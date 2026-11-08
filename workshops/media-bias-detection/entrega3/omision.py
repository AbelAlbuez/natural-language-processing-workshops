"""Cobertura u omisión por tema × gobierno sobre los eventos (paso 4).

Pregunta: en los eventos que cubren al menos tres medios, ¿qué medio falta en
qué temas, y cambia eso entre Duque y Petro más allá del cambio general?

Unidad: el evento (eventos.py, umbral 0,80), con su tema = el tópico de
BERTopic más frecuente en su núcleo. Para cada medio m:

    denominador        eventos en los que al menos k de los OTROS medios están
                       presentes (k = 3 con 5 medios). Así la entrada al
                       denominador no depende de m: en un evento de exactamente
                       3 medios, cada uno de los 3 es parte de la definición y
                       no puede «faltar», y el denominador ingenuo (eventos con
                       ≥3 medios) infla la participación de los medios que
                       suelen ser el tercero.
    participación      % del denominador en el que m está en el núcleo.
    omisión específica participación en el tema − participación general del
                       medio en ese gobierno (descuenta que publique menos en
                       general o que su archivo tenga huecos).
    Δ específico       omisión específica Petro − Duque.
    Δ relativo         Δ específico del medio − media del de los otros medios
                       (como `topics.relative_series`; suma 0 entre medios).

IC 95 % por bootstrap de bloques de 3 meses (20.000 réplicas, mismo esquema
circular que `topics.block_bootstrap_diff`), remuestreando meses de eventos y
recalculando los cocientes con los conteos agregados, y p-valores con Holm.

Ventana principal: los titulares de Noticias RCN anteriores a septiembre de
2020 sólo tienen fecha mensual y no entran en los eventos (que exigen fecha al
día), así que el gobierno Duque se restringe a 2020-09-01 → 2022-08-06 para
todos los medios. Robustez: sin restricción y sin RCN (periodo completo, 4
medios) y Duque desde mayo de 2021 (volumen de RCN normal). Cota de recall: un
medio ausente está «casi presente» si tenía un titular con similitud ≥ 0,75 (o
≥ 0,70) con algún titular del núcleo en ±2 días; incluye parejas ≥ 0,80 que no
entraron por no ser recíprocas o por estar en otro evento.

Uso: SCRIPT=omision.py ./run.sh - --output resultados_publico
"""

from __future__ import annotations

import argparse
import logging
import textwrap
import time
import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
from matplotlib.lines import Line2D
from matplotlib.ticker import PercentFormatter

import figuras
from figuras import (AXIS, BLUE, FUENTE, GOV_COLORS, GOV_NAMES, GRID, INK, INK2, MEDIA_NAMES, MUTED, NEUTRAL, NOTA_UMBRAL,
                     RED, SHORT, SURFACE, _margins, _save, miles)
from research_stats import holm_adjust
from topics import BOOTSTRAP_REPS, MEDIA, save_json

HERE = Path(__file__).resolve().parent
INICIO_RCN_DIA = pd.Timestamp("2020-09-01")  # desde aquí RCN tiene fecha al día en ≥ 80 % de sus titulares cada mes
INICIO_RCN_VOLUMEN = pd.Timestamp("2021-05-01")  # antes, RCN publica ~la mitad de su mediana mensual
TOPICOS_MIXTOS = {8: "mixto: no citar"}  # T8 de BERTopic mezcla temas (labels/publico_bertopic.csv)
UMBRALES_CASI = (0.75, 0.70)
VARIANTES_ROB = ("principal_k2", "sin_restriccion", "sin_restriccion_k2", "desde_2021_05", "desde_2021_05_k2",
                 "sin_rcn", "sin_rcn_ventana", "recall_0.75", "recall_0.70", "recall_0.75_k2", "recall_0.70_k2")


# ── núcleo del cálculo ───────────────────────────────────────────────────────


def presence_matrix(ev: pd.DataFrame, summary: pd.DataFrame, media=MEDIA) -> tuple[np.ndarray, pd.DataFrame]:
    """Matriz evento × medio (True si el medio está en el núcleo) y los datos del evento
    (gobierno, mes de inicio, tema). Sólo cuenta el núcleo, no el seguimiento."""
    core = ev[~ev["es_seguimiento"] & ev["source_id"].isin(media)]
    pres = pd.crosstab(core["event_id"], core["source_id"]).reindex(columns=list(media), fill_value=0) > 0
    meta = summary.set_index("event_id").loc[pres.index, ["gobierno", "fecha_inicio", "topic"]].copy()
    meta["fecha_inicio"] = pd.to_datetime(meta["fecha_inicio"])
    meta["mes"] = meta["fecha_inicio"].dt.to_period("M")
    return pres.to_numpy(), meta.reset_index()


def eligible(pres: np.ndarray, k: int) -> np.ndarray:
    """Evento × medio: True si al menos `k` de los OTROS medios están presentes.

    Con k = 3 y 5 medios es «el evento tendría ≥3 medios aunque faltara m»: la
    entrada al denominador no depende de la presencia de m."""
    total = pres.sum(axis=1, keepdims=True)
    return (total - pres) >= k


def naive_eligible(pres: np.ndarray, k: int) -> np.ndarray:
    """Denominador ingenuo: eventos con ≥ k medios en total, contando a m (sesgado)."""
    return np.repeat(pres.sum(axis=1, keepdims=True) >= k, pres.shape[1], axis=1)


def monthly_counts(months: np.ndarray, topics: np.ndarray, pres: np.ndarray, elig: np.ndarray,
                   month_list: list, n_topics: int) -> tuple[np.ndarray, np.ndarray]:
    """Conteos (mes, tema, medio): eventos en el denominador y eventos en los que participa."""
    pos = {m: i for i, m in enumerate(month_list)}
    mi = np.array([pos[m] for m in months], dtype=int)
    shape = (len(month_list), n_topics, pres.shape[1])
    den, num = np.zeros(shape), np.zeros(shape)
    for j in range(pres.shape[1]):
        np.add.at(den[:, :, j], (mi, topics), elig[:, j])
        np.add.at(num[:, :, j], (mi, topics), elig[:, j] & pres[:, j])
    return den, num


def shares(den: np.ndarray, num: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Participación por tema y general (en proporción) a partir de conteos ya sumados
    sobre los meses: den y num con forma (..., tema, medio)."""
    with np.errstate(invalid="ignore", divide="ignore"):
        topic = num / den
        general = num.sum(axis=-2) / den.sum(axis=-2)
    return topic, general


def relative(x: np.ndarray) -> np.ndarray:
    """Valor de cada medio (último eje) menos la media de los otros: suma 0 entre medios."""
    n = x.shape[-1]
    total = x.sum(axis=-1, keepdims=True)
    return x - (total - x) / (n - 1)


def block_weights(n_months: int, repetitions: int, block_length: int, rng) -> np.ndarray:
    """Cuántas veces entra cada mes en cada réplica (bloques móviles circulares, como
    `topics.block_bootstrap_diff`)."""
    blocks = int(np.ceil(n_months / block_length))
    starts = rng.integers(0, n_months, size=(repetitions, blocks))
    idx = ((starts[:, :, None] + np.arange(block_length)) % n_months).reshape(repetitions, -1)[:, :n_months]
    w = np.zeros((repetitions, n_months))
    np.add.at(w, (np.repeat(np.arange(repetitions), n_months), idx.ravel()), 1)
    return w


def _ci(draws: np.ndarray, repetitions: int):
    """IC 95 % percentil y p-valor bootstrap bilateral (temas sin eventos quedan en NaN)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        low, high = np.nanquantile(draws, [0.025, 0.975], axis=0)
    valid = ~np.isnan(draws)
    with np.errstate(invalid="ignore"):
        p = 2 * np.minimum((draws <= 0).sum(0) / valid.sum(0), (draws >= 0).sum(0) / valid.sum(0))
    return low, high, np.clip(p, 1 / repetitions, 1.0)


def analyze(pres: np.ndarray, elig: np.ndarray, meta: pd.DataFrame, media: list, n_topics: int,
            inferencia: np.ndarray | None = None, min_eventos: int = 30, repetitions: int = BOOTSTRAP_REPS,
            block_length: int = 3, seed: int = 42) -> dict:
    """Participación, omisión específica y Δ (específico y relativo) con IC por bootstrap.

    `inferencia` (vector de temas) fija qué temas se prueban; si es None, los que
    tienen ≥ `min_eventos` en el denominador de todos los medios en los dos gobiernos."""
    rng = np.random.default_rng(seed)
    obs, draws = {}, {}
    for gov in ("duque", "petro"):
        sel = (meta["gobierno"] == gov).to_numpy() & elig.any(axis=1)
        month_list = sorted(meta.loc[sel, "mes"].unique())
        den, num = monthly_counts(meta.loc[sel, "mes"].to_numpy(), meta.loc[sel, "topic"].to_numpy(),
                                  pres[sel], elig[sel], month_list, n_topics)
        topic, general = shares(den.sum(0), num.sum(0))
        obs[gov] = {"den": den.sum(0), "num": num.sum(0), "topic": topic, "general": general,
                    "esp": topic - general, "meses": len(month_list)}
        w = block_weights(len(month_list), repetitions, block_length, rng)
        den_b = (w @ den.reshape(len(month_list), -1)).reshape(repetitions, n_topics, len(media))
        num_b = (w @ num.reshape(len(month_list), -1)).reshape(repetitions, n_topics, len(media))
        t_b, g_b = shares(den_b, num_b)
        draws[gov] = {"esp": t_b - g_b[:, None, :], "general": g_b}
    if inferencia is None:
        inferencia = np.flatnonzero(np.minimum(obs["duque"]["den"], obs["petro"]["den"]).min(axis=1) >= min_eventos)
    inferencia = np.asarray(sorted(inferencia), dtype=int)

    rows = []
    for gov in ("duque", "petro"):
        lo, hi, _ = _ci(draws[gov]["esp"], repetitions)
        glo, ghi, _ = _ci(draws[gov]["general"], repetitions)
        for t in range(n_topics):
            for j, m in enumerate(media):
                d = obs[gov]["den"][t, j]
                rows.append({
                    "gobierno": gov, "topic": t, "source_id": m, "inferencia": bool(t in inferencia),
                    "eventos_denominador": int(d), "eventos_participa": int(obs[gov]["num"][t, j]),
                    "pct_participa": 100 * obs[gov]["topic"][t, j] if d else np.nan,
                    "pct_general": 100 * obs[gov]["general"][j],
                    "pct_general_low": 100 * glo[j], "pct_general_high": 100 * ghi[j],
                    "omision_especifica_pp": 100 * obs[gov]["esp"][t, j] if d else np.nan,
                    "omision_especifica_low_pp": 100 * lo[t, j] if d else np.nan,
                    "omision_especifica_high_pp": 100 * hi[t, j] if d else np.nan,
                })
    part = pd.DataFrame(rows)

    d_esp = obs["petro"]["esp"] - obs["duque"]["esp"]
    d_esp_b = draws["petro"]["esp"] - draws["duque"]["esp"]
    d_rel, d_rel_b = relative(d_esp), relative(d_esp_b)
    d_part = obs["petro"]["topic"] - obs["duque"]["topic"]
    elo, ehi, ep = _ci(d_esp_b, repetitions)
    rlo, rhi, rp = _ci(d_rel_b, repetitions)
    rows = []
    for t in inferencia:
        for j, m in enumerate(media):
            rows.append({
                "topic": int(t), "source_id": m,
                "eventos_duque": int(obs["duque"]["den"][t, j]), "eventos_petro": int(obs["petro"]["den"][t, j]),
                "pct_duque": 100 * obs["duque"]["topic"][t, j], "pct_petro": 100 * obs["petro"]["topic"][t, j],
                "delta_participa_pp": 100 * d_part[t, j],
                "delta_esp_pp": 100 * d_esp[t, j], "delta_esp_low_pp": 100 * elo[t, j],
                "delta_esp_high_pp": 100 * ehi[t, j], "delta_esp_p": float(ep[t, j]),
                "delta_rel_pp": 100 * d_rel[t, j], "delta_rel_low_pp": 100 * rlo[t, j],
                "delta_rel_high_pp": 100 * rhi[t, j], "delta_rel_p": float(rp[t, j]),
            })
    deltas = pd.DataFrame(rows)
    if len(deltas):
        deltas["delta_esp_p_holm"] = holm_adjust(deltas["delta_esp_p"].to_numpy())
        deltas["delta_rel_p_holm"] = holm_adjust(deltas["delta_rel_p"].to_numpy())
        check = deltas.groupby("topic")["delta_rel_pp"].sum().abs().max()
        if check > 1e-6:
            raise AssertionError(f"Δ relativo no suma 0 entre medios (máx {check})")
    d_gen = obs["petro"]["general"] - obs["duque"]["general"]
    glo, ghi, gp = _ci(draws["petro"]["general"] - draws["duque"]["general"], repetitions)
    general = pd.DataFrame([{"gobierno": g, "source_id": m, "pct_general": 100 * obs[g]["general"][j],
                             "eventos_denominador": int(obs[g]["den"][:, j].sum()), "meses": obs[g]["meses"],
                             "delta_general_pp": 100 * d_gen[j], "delta_general_low_pp": 100 * glo[j],
                             "delta_general_high_pp": 100 * ghi[j], "delta_general_p": float(gp[j])}
                            for g in ("duque", "petro") for j, m in enumerate(media)])
    return {"participacion": part, "deltas": deltas, "general": general, "inferencia": inferencia}


def near_present(ev: pd.DataFrame, aristas: pd.DataFrame, event_ids: np.ndarray, media=MEDIA) -> np.ndarray:
    """Evento × medio: la similitud más alta entre algún titular del núcleo y algún titular
    del medio en ±2 días (las aristas ≥ 0,60 de eventos.py; NaN si no hay ninguna)."""
    core = ev.loc[~ev["es_seguimiento"], ["event_id", "article_id"]]
    pairs = pd.concat([
        aristas.rename(columns={"article_id_a": "article_id", "medio_b": "medio"})[["article_id", "medio", "sim"]],
        aristas.rename(columns={"article_id_b": "article_id", "medio_a": "medio"})[["article_id", "medio", "sim"]],
    ])
    best = core.merge(pairs, on="article_id").groupby(["event_id", "medio"])["sim"].max().unstack()
    return best.reindex(index=event_ids, columns=list(media)).to_numpy(dtype=float)


# ── variantes y salidas ──────────────────────────────────────────────────────


def _load(out: Path):
    res = out / "eventos"
    ev = pd.read_parquet(res / "eventos.parquet")
    summary = pd.read_csv(res / "eventos_resumen.csv")
    labels_path = HERE / "labels" / "publico_bertopic.csv"
    labels = dict(pd.read_csv(labels_path)[["topic", "etiqueta"]].itertuples(index=False))
    return ev, summary, labels


def _label(labels: dict, t: int) -> str:
    return labels.get(t, f"T{t}") + (f" ({TOPICOS_MIXTOS[t]})" if t in TOPICOS_MIXTOS else "")


def _annotate(frame: pd.DataFrame, labels: dict, variante: str) -> pd.DataFrame:
    frame = frame.copy()
    frame.insert(0, "variante", variante)
    frame.insert(2, "etiqueta", frame["topic"].map(lambda t: _label(labels, t)))
    frame["citable"] = ~frame["topic"].isin(TOPICOS_MIXTOS)
    return frame


def run(args, out: Path) -> None:
    res = out / "omision"
    (res / "figuras").mkdir(parents=True, exist_ok=True)
    ev, summary, labels = _load(out)
    n_topics = int(summary["topic"].max()) + 1
    pres5, meta5 = presence_matrix(ev, summary)
    kw = {"repetitions": args.reps, "seed": args.seed, "min_eventos": args.min_eventos}

    # Principal: 5 medios, Duque desde que RCN tiene fecha al día; ≥3 de los otros 4.
    w = _window(meta5)
    meta_w = meta5[w].reset_index(drop=True)
    pres_w = pres5[w]
    principal = analyze(pres_w, eligible(pres_w, 3), meta_w, MEDIA, n_topics, **kw)
    variantes = {"principal": principal}
    # Sensibilidad: ≥2 de los otros 4 (con el medio evaluado serían ≥3): más eventos, temas y Holm propios.
    variantes["principal_k2"] = analyze(pres_w, eligible(pres_w, 2), meta_w, MEDIA, n_topics, **kw)
    naive = analyze(pres_w, naive_eligible(pres_w, 3), meta_w, MEDIA, n_topics, inferencia=principal["inferencia"],
                    **kw)
    # Robustez, sobre los temas de la sensibilidad (cada variante es su propia familia de Holm).
    inf = variantes["principal_k2"]["inferencia"]
    tardio = _window(meta5, INICIO_RCN_VOLUMEN)
    for k in (3, 2):
        suf = "" if k == 3 else "_k2"
        # (b) sin restricción: periodo completo.
        variantes[f"sin_restriccion{suf}"] = analyze(pres5, eligible(pres5, k), meta5, MEDIA, n_topics,
                                                     inferencia=inf, **kw)
        # Duque desde que el volumen de RCN se normaliza (mayo de 2021).
        variantes[f"desde_2021_05{suf}"] = analyze(pres5[tardio], eligible(pres5[tardio], k),
                                                   meta5[tardio].reset_index(drop=True), MEDIA, n_topics,
                                                   inferencia=inf, **kw)
    # (a) sin RCN: 4 medios; ≥2 de los otros 3 (con el medio evaluado serían ≥3).
    media4 = [m for m in MEDIA if m != "noticias_rcn"]
    pres4, meta4 = presence_matrix(ev, summary, media4)
    variantes["sin_rcn"] = analyze(pres4, eligible(pres4, 2), meta4, media4, n_topics, inferencia=inf, **kw)
    w4 = _window(meta4)
    variantes["sin_rcn_ventana"] = analyze(pres4[w4], eligible(pres4[w4], 2), meta4[w4].reset_index(drop=True),
                                           media4, n_topics, inferencia=inf, **kw)
    # Cota de recall: el ausente «casi presente» cuenta como presente (mismo denominador, del núcleo).
    aristas = pd.read_parquet(out / "eventos" / "aristas.parquet")
    near = near_present(ev, aristas, meta_w["event_id"].to_numpy())
    elig_w = eligible(pres_w, 3)
    for u in UMBRALES_CASI:
        up = pres_w | (near >= u)
        variantes[f"recall_{u:.2f}"] = analyze(up, elig_w, meta_w, MEDIA, n_topics, inferencia=inf, **kw)
        variantes[f"recall_{u:.2f}_k2"] = analyze(up, eligible(pres_w, 2), meta_w, MEDIA, n_topics,
                                                  inferencia=inf, **kw)

    part = pd.concat([_annotate(v["participacion"], labels, k) for k, v in variantes.items()])
    nv = naive["participacion"][["gobierno", "topic", "source_id", "eventos_denominador", "pct_participa",
                                 "pct_general"]].rename(columns={
        "eventos_denominador": "eventos_denominador_ingenuo", "pct_participa": "pct_participa_ingenuo",
        "pct_general": "pct_general_ingenuo"}).assign(variante="principal")
    part = part.merge(nv, on=["variante", "gobierno", "topic", "source_id"], how="left")
    part.to_csv(res / "participacion.csv", index=False)
    deltas = pd.concat([_annotate(v["deltas"], labels, k) for k, v in variantes.items()])
    deltas.to_csv(res / "deltas.csv", index=False)
    general = pd.concat([v["general"].assign(variante=k) for k, v in variantes.items()]
                        + [naive["general"].assign(variante="principal_denominador_ingenuo")])
    general.to_csv(res / "participacion_general.csv", index=False)

    rob = _robustness_table(deltas)
    rob.to_csv(res / "robustez_rcn.csv", index=False)
    cota = _recall_table(pres_w, elig_w, near, meta_w, args.umbral)
    cota.to_csv(res / "cota_recall.csv", index=False)
    rcn = _rcn_monthly(pres5, eligible(pres5, 3), meta5)
    rcn.to_csv(res / "rcn_participacion_mensual.csv", index=False)

    main = deltas[deltas["variante"] == "principal"]
    sig = main[(main["delta_rel_p_holm"] < 0.05) & main["citable"]]
    save_json(res / "omision.json", _summary_json(args, principal, naive, variantes, main, sig, rob, cota,
                                                 meta_w, pres_w, labels))

    fig_heatmap(part[part["variante"] == "principal"], labels, res, args.min_heatmap)
    fig_delta(deltas, labels, res)
    fig_robustez(general, rob, res)


def _window(meta: pd.DataFrame, inicio: pd.Timestamp = INICIO_RCN_DIA) -> np.ndarray:
    """Eventos de Petro y los de Duque desde `inicio`."""
    return ((meta["gobierno"] != "duque") | (meta["fecha_inicio"] >= inicio)).to_numpy()


def _robustness_table(deltas: pd.DataFrame) -> pd.DataFrame:
    cols = ["delta_rel_pp", "delta_rel_low_pp", "delta_rel_high_pp", "delta_rel_p", "delta_rel_p_holm"]
    wide = deltas.pivot_table(index=["topic", "etiqueta", "citable", "source_id"], columns="variante", values=cols)
    wide.columns = [f"{c}__{v}" for c, v in wide.columns]
    wide = wide.reset_index()
    # Signo de referencia: el principal, o el de ≥2 de los otros 4 donde el principal no tiene prueba.
    base = wide["delta_rel_pp__principal"].fillna(wide["delta_rel_pp__principal_k2"])
    for v in VARIANTES_ROB:
        if f"delta_rel_pp__{v}" not in wide:
            continue
        wide[f"mismo_signo__{v}"] = np.sign(wide[f"delta_rel_pp__{v}"]) == np.sign(base)
        wide[f"significativo__{v}"] = wide[f"delta_rel_p_holm__{v}"] < 0.05
    wide["significativo__principal"] = wide["delta_rel_p_holm__principal"] < 0.05
    return wide


def _recall_table(pres, elig, near, meta, umbral) -> pd.DataFrame:
    """Por medio y gobierno: ausencias en el denominador y cuántas son «casi presentes»."""
    rows = []
    for gov in ("duque", "petro"):
        g = (meta["gobierno"] == gov).to_numpy()
        for j, m in enumerate(MEDIA):
            absent = g & elig[:, j] & ~pres[:, j]
            row = {"gobierno": gov, "source_id": m, "eventos_denominador": int((g & elig[:, j]).sum()),
                   "ausencias": int(absent.sum())}
            for u in UMBRALES_CASI:
                n = int((absent & (near[:, j] >= u)).sum())
                row[f"casi_presente_{u:.2f}"] = n
                row[f"pct_ausencias_casi_{u:.2f}"] = 100 * n / max(absent.sum(), 1)
            # Ausente aunque tenía una pareja ≥ umbral: no fue recíproca o quedó en otro evento.
            row["pct_ausencias_con_pareja_ge_umbral"] = 100 * int((absent & (near[:, j] >= umbral)).sum()) / max(
                absent.sum(), 1)
            rows.append(row)
    return pd.DataFrame(rows)


def _rcn_monthly(pres, elig, meta) -> pd.DataFrame:
    j = MEDIA.index("noticias_rcn")
    frame = pd.DataFrame({"mes": meta["mes"].astype(str), "den": elig[:, j], "num": elig[:, j] & pres[:, j]})
    out = frame.groupby("mes")[["den", "num"]].sum()
    out["pct_participa"] = 100 * out["num"] / out["den"]
    return out.reset_index().rename(columns={"den": "eventos_denominador", "num": "eventos_participa"})


def _finding_rows(found: pd.DataFrame, rob: pd.DataFrame, prefix: str = "principal") -> list[dict]:
    """Cada hallazgo con su Δ relativo, IC y lo que da en las variantes de robustez."""
    rows = []
    for r in found.itertuples():
        rr = rob[(rob["topic"] == r.topic) & (rob["source_id"] == r.source_id)].iloc[0]
        rows.append({
            "medio": r.source_id, "topic": int(r.topic), "tema": r.etiqueta, "denominador": prefix,
            "delta_rel_pp": round(r.delta_rel_pp, 1),
            "ic95_pp": [round(r.delta_rel_low_pp, 1), round(r.delta_rel_high_pp, 1)],
            "p_holm": round(r.delta_rel_p_holm, 4), "pct_duque": round(r.pct_duque, 1),
            "pct_petro": round(r.pct_petro, 1),
            "variantes": {v: {"delta_rel_pp": round(float(rr[f"delta_rel_pp__{v}"]), 1),
                              "ic95_pp": [round(float(rr[f"delta_rel_low_pp__{v}"]), 1),
                                          round(float(rr[f"delta_rel_high_pp__{v}"]), 1)],
                              "significativo_holm": bool(rr[f"significativo__{v}"])}
                          for v in ("principal", *VARIANTES_ROB)
                          if f"delta_rel_pp__{v}" in rr and pd.notna(rr[f"delta_rel_pp__{v}"])},
        })
    return rows


def _summary_json(args, principal, naive, variantes, main, sig, rob, cota, meta_w, pres_w, labels) -> dict:
    gen = principal["general"].set_index(["gobierno", "source_id"])["pct_general"]
    gen_nv = naive["general"].set_index(["gobierno", "source_id"])["pct_general"]
    gen_full = variantes["sin_restriccion"]["general"].set_index(["gobierno", "source_id"])["pct_general"]
    sig_rows = _finding_rows(sig, rob)
    k2 = variantes["principal_k2"]["deltas"]
    k2 = k2[(k2["delta_rel_p_holm"] < 0.05) & ~k2["topic"].isin(TOPICOS_MIXTOS)]
    k2_rows = _finding_rows(k2.assign(etiqueta=k2["topic"].map(lambda t: _label(labels, t))), rob,
                            prefix="principal_k2")
    n3 = pres_w.sum(axis=1) >= 3
    return {
        "umbral_eventos": args.umbral, "inicio_ventana_duque": str(INICIO_RCN_DIA.date()),
        "inicio_volumen_normal_rcn": str(INICIO_RCN_VOLUMEN.date()),
        "temas_mixtos_excluidos_de_hallazgos": {str(k): v for k, v in TOPICOS_MIXTOS.items()},
        "bootstrap_reps": args.reps, "bloque_meses": 3, "min_eventos_por_celda": args.min_eventos,
        "eventos_3_o_mas_medios_ventana": {g: int(((meta_w["gobierno"] == g).to_numpy() & n3).sum())
                                           for g in ("duque", "petro")},
        "temas_con_inferencia": [int(t) for t in principal["inferencia"]],
        "pruebas_holm": int(len(main)), "p_min_ajustado_holm": len(main) / args.reps,
        "participacion_general_pct": {f"{g}/{s}": round(float(v), 1) for (g, s), v in gen.items()},
        "participacion_general_pct_denominador_ingenuo": {f"{g}/{s}": round(float(v), 1) for (g, s), v in gen_nv.items()},
        "participacion_general_pct_sin_restriccion": {f"{g}/{s}": round(float(v), 1) for (g, s), v in gen_full.items()},
        "delta_general_pp_principal": {
            r.source_id: {"delta": round(r.delta_general_pp, 1), "ic95": [round(r.delta_general_low_pp, 1),
                                                                          round(r.delta_general_high_pp, 1)]}
            for r in principal["general"][principal["general"]["gobierno"] == "duque"].itertuples()},
        "delta_rel_significativos_holm_0_05": int((main["delta_rel_p_holm"] < 0.05).sum()),
        "delta_esp_significativos_holm_0_05": int((main["delta_esp_p_holm"] < 0.05).sum()),
        "hallazgos_delta_rel_significativos_citables": sig_rows,
        "sensibilidad_k2": {
            "temas_con_inferencia": [int(t) for t in variantes["principal_k2"]["inferencia"]],
            "pruebas_holm": int(len(variantes["principal_k2"]["deltas"])),
            "significativos_holm_0_05_citables": k2_rows},
        "cota_recall_pct_ausencias_casi_presentes": {
            f"{r['gobierno']}/{r['source_id']}": {f"{u:.2f}": round(float(r[f"pct_ausencias_casi_{u:.2f}"]), 1)
                                                  for u in UMBRALES_CASI}
            for _, r in cota.iterrows()},
    }


# ── figuras ──────────────────────────────────────────────────────────────────


DIVERGING = LinearSegmentedColormap.from_list("div", [RED, "#f2b8b7", NEUTRAL, "#b5d1f5", BLUE])
NOTA_DEN = ("Denominador de cada medio: eventos con al menos 3 de los OTROS 4 medios presentes (la entrada no "
            "depende del medio evaluado). Duque restringido a 2020-09 → 2022-08 (antes RCN sólo tiene fecha mensual).")


def _ylabel(labels: dict, t: int) -> str:
    return f"T{t} mixto (no citar)" if t in TOPICOS_MIXTOS else labels.get(t, f"T{t}")


def fig_heatmap(part: pd.DataFrame, labels: dict, res: Path, min_eventos: int) -> None:
    n = part.groupby("topic")["eventos_denominador"].min()
    part = part[part["topic"].isin(n[n >= min_eventos].index)]
    order = (part.groupby("topic")["eventos_denominador"].sum().sort_values(ascending=False).index.tolist())
    cols = [(m, g) for m in MEDIA for g in ("duque", "petro")]
    val = part.set_index(["topic", "source_id", "gobierno"])["omision_especifica_pp"]
    lo = part.set_index(["topic", "source_id", "gobierno"])["omision_especifica_low_pp"]
    hi = part.set_index(["topic", "source_id", "gobierno"])["omision_especifica_high_pp"]
    mat = np.array([[val[(t, m, g)] for m, g in cols] for t in order])
    vmax = np.nanmax(np.abs(mat))
    fig, ax = plt.subplots(figsize=(11.5, 0.42 * len(order) + 2.2))
    ax.imshow(mat, cmap=DIVERGING, norm=TwoSlopeNorm(0, -vmax, vmax), aspect="auto")
    for i, t in enumerate(order):
        for j, (m, g) in enumerate(cols):
            v = mat[i, j]
            sure = lo[(t, m, g)] > 0 or hi[(t, m, g)] < 0
            ax.text(j, i, f"{round(v) + 0:+d}".replace("-", "−"), ha="center", va="center", fontsize=8,
                    color=SURFACE if abs(v) > vmax * 0.6 else INK, fontweight="bold" if sure else "normal")
    for j in range(2, len(cols), 2):
        ax.axvline(j - 0.5, color=SURFACE, lw=3)
    ax.set_xticks(range(len(cols)), [f"{SHORT[m]}\n{GOV_NAMES[g]}" for m, g in cols], fontsize=8)
    inf = set(part.loc[part["inferencia"], "topic"])
    ax.set_yticks(range(len(order)), [f"{'* ' if t in inf else ''}{_ylabel(labels, t)}  (n ≥ {n[t]})"
                                      for t in order], fontsize=8)
    for tick, t in zip(ax.get_yticklabels(), order):
        if t in TOPICOS_MIXTOS:
            tick.set_color(MUTED)
    ax.xaxis.tick_top()
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    _margins(fig, [
        Line2D([], [], marker="s", ls="", color=BLUE, markersize=9, label="participa más en el tema que en general"),
        Line2D([], [], marker="s", ls="", color=RED, markersize=9, label="participa menos (omite más) en el tema"),
    ], ncol=2, top_in=1.2, bottom_in=0.3)
    _save(fig, res, "23_omision_especifica.png", "Qué medio falta en qué tema, en cada gobierno",
          "Omisión específica = % de eventos del tema en los que el medio participa − su % en todos los eventos, en "
          "puntos porcentuales. Negrita: IC 95 % (bootstrap de bloques de 3 meses) no cruza 0, sin corregir. "
          f"n = menor denominador del tema entre medios y gobiernos; sólo temas con n ≥ {min_eventos}; * = n ≥ 30, "
          f"con prueba de Δ (figura 24). Descriptivo. {NOTA_DEN} {NOTA_UMBRAL} {FUENTE}")


def fig_delta(deltas: pd.DataFrame, labels: dict, res: Path) -> None:
    """Δ relativo con IC: denominador principal (≥3 de los otros 4) y sensibilidad (≥2 de los otros 4)."""
    k3 = deltas[deltas["variante"] == "principal"]
    k2 = deltas[deltas["variante"] == "principal_k2"]
    order = (k2.groupby("topic")["delta_rel_pp"].apply(lambda s: s.abs().max()).sort_values().index.tolist())
    order = [t for t in order if t in TOPICOS_MIXTOS] + [t for t in order if t not in TOPICOS_MIXTOS]
    fig, axes = plt.subplots(1, len(MEDIA), figsize=(16, 0.42 * len(order) + 2.6), sharey=True, sharex=True)
    y = np.arange(len(order))
    for ax, m in zip(axes, MEDIA):
        for frame, dy, marker in ((k3, 0.17, "o"), (k2, -0.17, "s")):
            d = frame[frame["source_id"] == m].set_index("topic").reindex(order)
            ok = d["delta_rel_pp"].notna().to_numpy()
            color = np.where(d["delta_rel_pp"] >= 0, BLUE, RED)
            color = np.where(np.isin(order, list(TOPICOS_MIXTOS)), AXIS, color)
            ax.hlines(y[ok] + dy, d["delta_rel_low_pp"][ok], d["delta_rel_high_pp"][ok], color=color[ok], lw=1.4)
            sig = ok & (d["delta_rel_p_holm"] < 0.05).to_numpy()
            ax.scatter(d["delta_rel_pp"][sig], y[sig] + dy, color=color[sig], marker=marker, s=46, zorder=3,
                       edgecolor=SURFACE, lw=0.6)
            ns = ok & ~sig
            ax.scatter(d["delta_rel_pp"][ns], y[ns] + dy, facecolor=SURFACE, edgecolor=color[ns], marker=marker,
                       s=38, zorder=3, lw=1.4)
        ax.axvline(0, color=INK2, lw=1)
        ax.set_title(MEDIA_NAMES[m])
        ax.grid(axis="y", visible=False)
        ax.set_xlabel("puntos porcentuales")
    axes[0].set_yticks(y, [_ylabel(labels, t) for t in order], fontsize=8)
    for tick, t in zip(axes[0].get_yticklabels(), order):
        if t in TOPICOS_MIXTOS:
            tick.set_color(MUTED)
    _margins(fig, [
        Line2D([], [], marker="o", ls="", color=BLUE, label="con Petro, falta menos en el tema que los otros"),
        Line2D([], [], marker="o", ls="", color=RED, label="con Petro, falta más en el tema que los otros"),
        Line2D([], [], marker="o", ls="", markerfacecolor=SURFACE, markeredgecolor=INK2,
               label="no significativo (Holm ≥ 0,05)"),
        Line2D([], [], marker="o", ls="", color=INK2, label="≥3 de los otros 4 (principal)"),
        Line2D([], [], marker="s", ls="", color=INK2, label="≥2 de los otros 4 (sensibilidad)"),
    ], ncol=3, top_in=1.0)
    _save(fig, res, "24_omision_delta_relativo.png",
          "Cambio de Duque a Petro en la omisión por tema, más allá del cambio general",
          "Δ relativo = (omisión específica Petro − Duque) del medio menos la media de los otros cuatro; barras = IC 95 % "
          "por bootstrap de bloques de 3 meses (20.000 réplicas); relleno = significativo tras Holm (cada denominador "
          "es su propia familia). Círculo: sólo temas con ≥30 eventos en cada celda con el denominador principal. "
          "En gris, el tópico mixto. Duque restringido a 2020-09 → 2022-08 (antes RCN sólo tiene fecha mensual). "
          f"{NOTA_UMBRAL} {FUENTE}")


VARIANTES_FIG = [("principal", "Principal: ≥3 de los otros 4, Duque desde 2020-09", "o", INK),
                 ("principal_k2", "≥2 de los otros 4 (base de las siguientes)", "s", INK),
                 ("sin_restriccion_k2", "Sin restringir el periodo", "D", INK2),
                 ("desde_2021_05_k2", "Duque desde 2021-05 (volumen de RCN normal)", "P", INK2),
                 ("sin_rcn", "Sin RCN, periodo completo (≥2 de los otros 3)", "v", MUTED),
                 ("recall_0.75_k2", "Ausente con titular ≥ 0,75 con el núcleo cuenta como presente", "^", MUTED)]


def fig_robustez(general: pd.DataFrame, rob: pd.DataFrame, res: Path) -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6), gridspec_kw={"width_ratios": [1, 1.25]})
    # Izquierda: participación general por medio, ventana principal frente a periodo completo.
    x = np.arange(len(MEDIA))
    width = 0.27
    combos = [("sin_restriccion", "duque", "Duque, periodo completo", 0.4),
              ("principal", "duque", "Duque desde 2020-09", 1.0),
              ("principal", "petro", "Petro", 1.0)]
    handles = []
    for i, (v, g, lab, alpha) in enumerate(combos):
        d = general[(general["variante"] == v) & (general["gobierno"] == g)].set_index("source_id").loc[MEDIA]
        bars = ax1.bar(x + (i - 1) * width, d["pct_general"], width, color=GOV_COLORS[g], alpha=alpha,
                       edgecolor=SURFACE, linewidth=2, label=lab)
        handles.append(bars)
        for b, val in zip(bars, d["pct_general"]):
            ax1.text(b.get_x() + b.get_width() / 2, val + 1, f"{val:.0f}", ha="center", va="bottom", fontsize=7.5,
                     color=INK2)
    ax1.set_xticks(x, [SHORT[m] for m in MEDIA])
    ax1.set_ylim(0, 100)
    ax1.yaxis.set_major_formatter(PercentFormatter(100, decimals=0))
    ax1.set_title("Participación general: el hueco de fechas de RCN")
    ax1.grid(axis="x", visible=False)
    ax1.legend(handles=handles, loc="upper right", fontsize=8)
    # Derecha: Δ relativo de los cruces candidatos (p sin ajustar < 0,10 en la principal) en cada variante.
    cand = rob[rob["citable"] & ((rob["delta_rel_p__principal"] < 0.05) | (rob["delta_rel_p_holm__principal"] < 0.05)
                                 | (rob["delta_rel_p_holm__principal_k2"] < 0.05))].copy()
    cand = cand.reindex(cand["delta_rel_pp__principal_k2"].sort_values().index)
    y = np.arange(len(cand))
    off = np.linspace(0.33, -0.33, len(VARIANTES_FIG))
    hand2 = []
    for k, (v, lab, marker, tone) in enumerate(VARIANTES_FIG):
        val, lo, hi = cand[f"delta_rel_pp__{v}"], cand[f"delta_rel_low_pp__{v}"], cand[f"delta_rel_high_pp__{v}"]
        ok = val.notna().to_numpy()
        ax2.hlines(y[ok] + off[k], lo[ok], hi[ok], color=tone, lw=1.2)
        filled = (cand[f"delta_rel_p_holm__{v}"] < 0.05).to_numpy() & ok
        ax2.scatter(val[filled], y[filled] + off[k], marker=marker, color=tone, s=58, zorder=3, edgecolor=SURFACE,
                    lw=0.6)
        ax2.scatter(val[ok & ~filled], y[ok & ~filled] + off[k], marker=marker, facecolor=SURFACE,
                    edgecolor=tone, s=34, zorder=3, lw=1.3)
        hand2.append(Line2D([], [], marker=marker, ls="-", color=tone, lw=1.2, label=lab))
    ax2.axvline(0, color=INK2, lw=1)
    ax2.set_yticks(y, [f"{SHORT[s]} · {textwrap.shorten(e, 40, placeholder='…')}"
                       for s, e in zip(cand["source_id"], cand["etiqueta"])], fontsize=8)
    for yy in y[:-1]:
        ax2.axhline(yy + 0.5, color=GRID, lw=0.8)
    ax2.set_xlabel("Δ relativo (Petro − Duque), puntos porcentuales")
    ax2.set_title("Cruces medio × tema candidatos: ¿se sostienen?")
    ax2.grid(axis="y", visible=False)
    ax2.legend(handles=hand2, loc="upper center", bbox_to_anchor=(0.45, -0.12), ncol=2, fontsize=8)
    fig.subplots_adjust(wspace=0.5, top=0.93)
    _save(fig, res, "25_omision_robustez.png", "Robustez: fechas de RCN y recall del emparejamiento",
          "Izquierda: % de eventos (denominador: ≥3 de los otros 4 medios) en los que participa cada medio; antes de "
          "2020-09 los titulares de RCN sólo tienen fecha mensual y no entran en los eventos. Derecha: cruces "
          "significativos tras Holm con alguno de los dos denominadores, o con p sin ajustar < 0,05 en el principal; "
          "Δ relativo e IC 95 % en cada variante; relleno = significativo tras Holm en esa variante (familia de 75 "
          f"pruebas en las de robustez). {NOTA_UMBRAL} {FUENTE}", note_y=-0.2)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, default=HERE / "resultados_publico")
    parser.add_argument("--umbral", type=float, default=0.80, help="Umbral con el que se armaron los eventos")
    parser.add_argument("--min-eventos", type=int, default=30,
                        help="Mínimo de eventos en el denominador (cada medio y gobierno) para hacer inferencia")
    parser.add_argument("--min-heatmap", type=int, default=15,
                        help="Mínimo de eventos en cada celda para mostrar un tema en la figura 23 (descriptiva)")
    parser.add_argument("--reps", type=int, default=BOOTSTRAP_REPS)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    t0 = time.monotonic()
    run(args, args.output.resolve())
    logging.info("omisión terminada en %.0f s", time.monotonic() - t0)


if __name__ == "__main__":
    main()
