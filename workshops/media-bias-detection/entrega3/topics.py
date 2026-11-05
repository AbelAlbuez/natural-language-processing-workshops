"""LDA conjunto Duque + Petro sobre titulares reconstruidos desde el slug.

Etapas (reanudables, cada una lee lo que dejó la anterior en --output):

    prepare    filtra, tokeniza, une bigramas, muestra balanceada, diccionario
    train      grilla de K con LdaMulticore; c_v y perplejidad en held-out
    stability  re-entrena el K elegido con otras semillas y empareja tópicos
    infer      distribución de tópicos para los ~1,57 M de titulares
    examples   palabras y titulares de ejemplo para etiquetar cada tópico
    robustness Δ relativo recalculado con los modelos de las otras semillas
    compare    participación por medio y gobierno, Δ y Δ relativo, JS

El modelo se entrena con una muestra balanceada (mismo número de titulares por
medio × gobierno) para que ni El Tiempo (40 % del corpus) ni Petro (+37 % de
titulares) definan los tópicos por volumen; después se infiere sobre todo.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import time
from functools import partial
from pathlib import Path

import numpy as np
import pandas as pd
from gensim.corpora import Dictionary
from gensim.models import CoherenceModel, LdaModel, LdaMulticore
from gensim.models.phrases import Phrases
from nltk.corpus import stopwords
from scipy.optimize import linear_sum_assignment
from scipy.spatial.distance import jensenshannon

from core import fold, tokenize
from research_stats import holm_adjust

import figuras

MEDIA = ["el_tiempo", "blu_radio", "noticias_rcn", "noticias_caracol", "la_republica"]
GOVS = ["duque", "petro"]
COLUMNS = [
    "article_id", "url", "source_id", "government_id", "title", "title_source",
    "published_date", "date_precision", "non_news_reason",
]
HERE = Path(__file__).resolve().parent
KEEP_WORDS = {"estado", "estados"}
# Robustez de un tópico = Jaccard medio de sus 10 palabras principales con el
# tópico emparejado en cada semilla alternativa.
ROBUSTO, PARCIAL = 0.5, 0.3


# ── utilidades ───────────────────────────────────────────────────────────────


def save_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(partial(stream.read, 1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def stop_words() -> set[str]:
    domain = [
        line.strip() for line in (HERE / "stopwords_dominio.txt").read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]
    # NLTK lista "estado(s)" como formas de *estar*; en titulares casi siempre es
    # "Estados Unidos" o "el Estado", y quitarlo dejaba "unidos" suelto.
    nltk_es = {fold(w) for w in stopwords.words("spanish")} - KEEP_WORDS
    return nltk_es | {fold(w) for w in domain}


def balanced_sample(frame: pd.DataFrame, per_cell: int, seed: int) -> pd.Index:
    """Índices de una muestra con `per_cell` titulares por medio × gobierno."""
    sizes = frame.groupby(["source_id", "government_id"]).size()
    if (sizes < per_cell).any():
        raise ValueError(f"Celdas con menos de {per_cell} titulares:\n{sizes[sizes < per_cell]}")
    return (
        frame.groupby(["source_id", "government_id"], group_keys=False)
        .sample(n=per_cell, random_state=seed)
        .index
    )


def topic_similarity(first: np.ndarray, second: np.ndarray) -> np.ndarray:
    """1 − distancia Jensen-Shannon (base 2) entre las filas de dos matrices tópico-palabra."""
    return np.array([[1 - jensenshannon(a, b, base=2) for b in second] for a in first])


def match_topics(first: np.ndarray, second: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Empareja tópicos de dos modelos (Hungarian, máxima similitud).

    Devuelve, para cada tópico de `first`, el índice emparejado en `second` y su
    similitud.
    """
    similarity = topic_similarity(first, second)
    rows, cols = linear_sum_assignment(-similarity)
    order = np.argsort(rows)
    return cols[order], similarity[rows[order], cols[order]]


def block_bootstrap_diff(after, before, repetitions=2000, block_length=3, seed=42) -> dict:
    """Diferencia de medias (after − before) de dos series mensuales, con IC por
    bootstrap de bloques móviles (mismo esquema que `research_stats.block_bootstrap_mean`)
    y p-valor bootstrap bilateral."""
    rng = np.random.default_rng(seed)

    def resample(values):
        values = np.asarray(values, dtype=float)
        blocks = int(np.ceil(len(values) / block_length))
        starts = rng.integers(0, len(values), size=(repetitions, blocks))
        idx = ((starts[:, :, None] + np.arange(block_length)) % len(values)).reshape(repetitions, -1)
        return values[idx[:, : len(values)]].mean(axis=1)

    diffs = resample(after) - resample(before)
    observed = float(np.mean(after) - np.mean(before))
    low, high = np.quantile(diffs, [0.025, 0.975])
    p = float(min(1.0, 2 * min((diffs <= 0).mean(), (diffs >= 0).mean())))
    return {"delta": observed, "low": float(low), "high": float(high), "p": max(p, 1 / repetitions)}


def relative_series(shares: pd.DataFrame) -> pd.DataFrame:
    """Para cada medio: su participación menos la media de los otros medios.

    `shares` tiene una columna por medio (filas = meses). Por construcción, la
    suma de las series relativas de todos los medios es cero en cada mes.
    """
    n = shares.shape[1]
    total = shares.sum(axis=1)
    return shares.apply(lambda col: col - (total - col) / (n - 1))


def doc_topics(model: LdaModel, bows: list, chunk: int = 20000) -> np.ndarray:
    """Distribución de tópicos θ por documento, vectorizada por lotes."""
    theta = np.empty((len(bows), model.num_topics), dtype=np.float32)
    for start in range(0, len(bows), chunk):
        gamma, _ = model.inference(bows[start : start + chunk])
        theta[start : start + chunk] = gamma / gamma.sum(axis=1, keepdims=True)
    return theta


def jaccard_top(model_a: LdaModel, topic_a: int, model_b: LdaModel, topic_b: int, n: int = 10) -> float:
    a = {w for w, _ in model_a.show_topic(topic_a, n)}
    b = {w for w, _ in model_b.show_topic(topic_b, n)}
    return len(a & b) / len(a | b)


def robustness_class(jaccard_mean: float) -> str:
    if jaccard_mean >= ROBUSTO:
        return "robusto"
    return "parcial" if jaccard_mean >= PARCIAL else "inestable"


def monthly_shares(theta: np.ndarray, meta: pd.DataFrame) -> pd.DataFrame:
    """Media de θ por gobierno × mes × medio (columnas t0..tK)."""
    topics = [f"t{k}" for k in range(theta.shape[1])]
    frame = pd.concat([meta[["government_id", "month", "source_id"]].reset_index(drop=True),
                       pd.DataFrame(theta, columns=topics)], axis=1)
    return frame.groupby(["government_id", "month", "source_id"])[topics].mean()


def relative_delta_points(monthly: pd.DataFrame, column: str) -> pd.Series:
    """Δ relativo (Petro − Duque, en pp) por medio para una columna de tópico."""
    wide = monthly[column].unstack("source_id")[MEDIA].dropna()
    rel = relative_series(wide)
    return 100 * (rel.loc["petro"].mean() - rel.loc["duque"].mean())


# ── etapas ───────────────────────────────────────────────────────────────────


def stage_prepare(args, out: Path) -> None:
    raw = pd.read_parquet(args.input, columns=COLUMNS)
    funnel = [("Export 2018-08 → 2026-08 (todos los medios)", len(raw))]
    frame = raw[raw["government_id"].isin(GOVS)]
    funnel.append(("Gobierno Duque o Petro", len(frame)))
    frame = frame[frame["source_id"].isin(MEDIA)]
    funnel.append(("5 medios con los dos gobiernos", len(frame)))
    frame = frame[frame["title"].notna()]
    funnel.append(("Con titular", len(frame)))
    frame = frame[frame["non_news_reason"].isna()].reset_index(drop=True)
    funnel.append(("Noticias (sin marca de no-noticia)", len(frame)))
    del raw

    frame["published_date"] = pd.to_datetime(frame["published_date"])
    frame["month"] = frame["published_date"].dt.to_period("M").dt.to_timestamp()

    logging.info("Tokenizando %s titulares", len(frame))
    nltk_only = {fold(w) for w in stopwords.words("spanish")} - KEEP_WORDS
    stops = stop_words()
    frame["tokens"] = frame["title"].map(partial(tokenize, stop_words=stops))

    sample_idx = balanced_sample(frame, args.per_cell, args.seed)
    frame["in_sample"] = frame.index.isin(sample_idx)
    funnel.append((f"Muestra de entrenamiento ({figuras.miles(args.per_cell)} × 10 celdas)", int(frame["in_sample"].sum())))

    # Held-out balanceado, disjunto de la muestra, para la perplejidad.
    rest = frame[~frame["in_sample"]]
    heldout_idx = balanced_sample(rest, args.heldout_per_cell, args.seed + 1)
    frame["in_heldout"] = frame.index.isin(heldout_idx)

    logging.info("Entrenando Phrases sobre la muestra")
    phrases = Phrases(frame.loc[frame["in_sample"], "tokens"], min_count=50, threshold=10.0)
    frozen = phrases.freeze()
    frozen.save(str(out / "modelos" / "phrases.pkl"))
    frame["tokens"] = [frozen[t] for t in frame["tokens"]]

    dictionary = Dictionary(frame.loc[frame["in_sample"], "tokens"])
    dictionary.filter_extremes(no_below=args.no_below, no_above=args.no_above, keep_n=args.keep_n)
    dictionary.save(str(out / "modelos" / "dictionary.dict"))

    # Figura 04: frecuencia documental antes (sólo NLTK) y después (dominio + Phrases).
    probe = frame.sample(200_000, random_state=args.seed)
    before = pd.Series([w for t in probe["title"] for w in set(tokenize(t, nltk_only))]).value_counts()
    after = pd.Series([w for t in probe["tokens"] for w in set(t)]).value_counts()
    removed = set(before.index) - set(after.index)
    bigrams = [w for w in after.index if "_" in w][:15]
    figuras.tokens_antes_despues(before.head(20), after.head(20), removed, bigrams, len(probe), out)

    keep = [
        "article_id", "url", "source_id", "government_id", "title", "published_date", "month",
        "date_precision", "tokens", "in_sample", "in_heldout",
    ]
    frame[keep].to_parquet(out / "prepared.parquet", index=False)

    cells = frame.groupby(["source_id", "government_id"]).size().rename("disponibles").reset_index()
    cells.to_csv(out / "celdas.csv", index=False)
    monthly = frame.groupby(["source_id", "month"]).size().rename("titulares").reset_index()
    monthly.to_csv(out / "volumen_mensual.csv", index=False)

    figuras.embudo(funnel, out)
    figuras.volumen_mensual(monthly, out)
    figuras.muestra_balanceada(cells, args.per_cell, out)

    save_json(out / "prepare.json", {
        "funnel": funnel,
        "vocabulario": len(dictionary),
        "bigramas_en_vocabulario": sum("_" in w for w in dictionary.token2id),
        "ejemplos_bigramas": bigrams,
        "sin_tokens": int(frame["tokens"].map(len).eq(0).sum()),
        "tokens_por_titular_media": float(frame["tokens"].map(len).mean()),
        "por_celda": args.per_cell,
        "heldout_por_celda": args.heldout_per_cell,
    })
    logging.info("prepare: %s titulares, vocabulario %s", len(frame), len(dictionary))


def _load_prepared(out: Path, columns=None) -> pd.DataFrame:
    return pd.read_parquet(out / "prepared.parquet", columns=columns)


def _train_one(bows, dictionary, k, seed, args):
    return LdaMulticore(
        corpus=bows, id2word=dictionary, num_topics=k, workers=args.workers,
        passes=args.passes, iterations=100, chunksize=4000, random_state=seed,
        eval_every=None, minimum_probability=0.0,
    )


def stage_train(args, out: Path) -> None:
    frame = _load_prepared(out, ["tokens", "in_sample", "in_heldout"])
    dictionary = Dictionary.load(str(out / "modelos" / "dictionary.dict"))
    sample = [t.tolist() for t in frame.loc[frame["in_sample"], "tokens"]]
    heldout = [dictionary.doc2bow(t.tolist()) for t in frame.loc[frame["in_heldout"], "tokens"]]
    heldout = [b for b in heldout if b]
    bows = [dictionary.doc2bow(t) for t in sample]
    keep = [i for i, b in enumerate(bows) if b]
    bows = [bows[i] for i in keep]
    texts = [sample[i] for i in keep]
    rng = np.random.default_rng(args.seed)
    cv_texts = [texts[i] for i in rng.choice(len(texts), size=min(args.cv_docs, len(texts)), replace=False)]
    del frame

    rows = []
    for k in args.topics:
        path = out / "modelos" / f"lda_k{k}.model"
        t0 = time.monotonic()
        if path.exists():
            model = LdaModel.load(str(path))
        else:
            logging.info("Entrenando K=%s sobre %s titulares", k, len(bows))
            model = _train_one(bows, dictionary, k, args.seed, args)
            model.save(str(path))
        train_s = time.monotonic() - t0
        cv = CoherenceModel(
            model=model, texts=cv_texts, dictionary=dictionary, coherence="c_v",
            topn=10, processes=args.workers,
        ).get_coherence()
        bound = model.log_perplexity(heldout)
        rows.append({
            "K": k, "coherence_cv": float(cv), "heldout_log_perplexity": float(bound),
            "heldout_perplexity": float(2 ** -bound), "segundos_entrenamiento": round(train_s, 1),
        })
        logging.info("K=%s c_v=%.4f perplejidad=%.1f", k, cv, 2 ** -bound)
        pd.DataFrame(rows).to_csv(out / "lda_optimization.csv", index=False)

    scores = pd.DataFrame(rows)
    best = int(scores.loc[scores["coherence_cv"].idxmax(), "K"])
    save_json(out / "train.json", {
        "best_k": best, "criterio": "máximo c_v (top 10, 100k textos de la muestra)",
        "documentos_entrenamiento": len(bows), "documentos_heldout": len(heldout),
        "passes": args.passes, "iterations": 100, "seed": args.seed,
    })
    figuras.seleccion_k(scores, best, out)


def stage_stability(args, out: Path) -> None:
    best = args.k or load_json(out / "train.json")["best_k"]
    frame = _load_prepared(out, ["tokens", "in_sample"])
    dictionary = Dictionary.load(str(out / "modelos" / "dictionary.dict"))
    bows = [b for b in (dictionary.doc2bow(t.tolist()) for t in frame.loc[frame["in_sample"], "tokens"]) if b]
    del frame
    base_model = LdaModel.load(str(out / "modelos" / f"lda_k{best}.model"))
    base = base_model.get_topics()
    rows, matrices, jaccards = [], {}, {}
    for seed in args.stability_seeds:
        path = out / "modelos" / f"lda_k{best}_seed{seed}.model"
        if path.exists():
            other = LdaModel.load(str(path))
        else:
            logging.info("Estabilidad: K=%s semilla %s", best, seed)
            other = _train_one(bows, dictionary, best, seed, args)
            other.save(str(path))
        other_topics = other.get_topics()
        matched, sims = match_topics(base, other_topics)
        matrices[seed] = topic_similarity(base, other_topics[matched])
        jac = np.array([jaccard_top(base_model, t, other, int(m)) for t, m in enumerate(matched)])
        jaccards[seed] = jac
        rows.extend({"topic": t, "seed": seed, "matched_topic": int(m), "similitud_js": float(sm),
                     "jaccard_top10": float(j)}
                    for t, (m, sm, j) in enumerate(zip(matched, sims, jac)))
    table = pd.DataFrame(rows)
    table.to_csv(out / "topic_stability.csv", index=False)
    robust = table.groupby("topic").agg(jaccard_medio=("jaccard_top10", "mean"),
                                        similitud_js_min=("similitud_js", "min"))
    robust["robustez"] = robust["jaccard_medio"].map(robustness_class)
    robust.to_csv(out / "topic_robustness.csv")
    save_json(out / "stability.json", {
        "k": best, "seeds": args.stability_seeds,
        "criterio": f"Jaccard medio de las 10 palabras principales: robusto ≥ {ROBUSTO}, parcial ≥ {PARCIAL}",
        "conteo": robust["robustez"].value_counts().to_dict(),
        "jaccard_medio_global": float(robust["jaccard_medio"].mean()),
        "similitud_js_media": float(table["similitud_js"].mean()),
    })
    figuras.estabilidad(matrices, jaccards, out)


def stage_infer(args, out: Path) -> None:
    best = args.k or load_json(out / "train.json")["best_k"]
    model = LdaModel.load(str(out / "modelos" / f"lda_k{best}.model"))
    frame = _load_prepared(out, ["article_id", "source_id", "government_id", "month", "tokens"])
    dictionary = model.id2word
    bows = [dictionary.doc2bow(t.tolist()) for t in frame["tokens"]]
    empty = np.array([not b for b in bows])
    logging.info("Infiriendo %s titulares (%s sin vocabulario)", len(bows), empty.sum())
    theta = doc_topics(model, bows)
    theta[empty] = np.nan
    np.save(out / "theta.npy", theta)
    assign = frame[["article_id", "source_id", "government_id", "month"]].copy()
    assign["dominant_topic"] = np.where(empty, -1, np.nan_to_num(theta).argmax(axis=1))
    assign["topic_confidence"] = np.where(empty, 0.0, np.nan_to_num(theta).max(axis=1))
    assign.to_parquet(out / "document_topics.parquet", index=False)

    conf = assign[assign["dominant_topic"] >= 0]
    table = conf.groupby("source_id")["topic_confidence"].describe(percentiles=[0.25, 0.5, 0.75])
    table["pct_menor_0_3"] = conf.groupby("source_id")["topic_confidence"].apply(lambda s: 100 * (s < 0.3).mean())
    table["sin_vocabulario"] = assign.groupby("source_id")["dominant_topic"].apply(lambda s: int((s < 0).sum()))
    table.to_csv(out / "topic_confidence.csv")
    figuras.confianza(conf, out)
    save_json(out / "infer.json", {
        "k": best, "documentos": len(assign), "sin_vocabulario": int(empty.sum()),
        "confianza_media": float(conf["topic_confidence"].mean()),
        "pct_confianza_menor_0_3": float(100 * (conf["topic_confidence"] < 0.3).mean()),
    })

    # pyLDAvis sobre la muestra de entrenamiento: con 1,57 M no es manejable.
    import pyLDAvis

    sample_mask = _load_prepared(out, ["in_sample"])["in_sample"].to_numpy() & ~empty
    sbows = [bows[i] for i in np.flatnonzero(sample_mask)]
    term_frequency = np.zeros(len(dictionary), dtype=np.int64)
    for bow in sbows:
        for term_id, count in bow:
            term_frequency[term_id] += count
    vis = pyLDAvis.prepare(
        topic_term_dists=model.get_topics(), doc_topic_dists=theta[sample_mask],
        doc_lengths=[sum(c for _, c in b) for b in sbows],
        vocab=[dictionary[i] for i in range(len(dictionary))], term_frequency=term_frequency,
        mds="mmds", sort_topics=False, n_jobs=1,
    )
    pyLDAvis.save_html(vis, str(out / "lda_visualization.html"))


def stage_examples(args, out: Path) -> None:
    best = args.k or load_json(out / "train.json")["best_k"]
    model = LdaModel.load(str(out / "modelos" / f"lda_k{best}.model"))
    theta = np.load(out / "theta.npy")
    frame = _load_prepared(out, ["article_id", "source_id", "government_id", "title", "tokens"])
    ntok = frame["tokens"].map(len).to_numpy()
    terms, examples = [], []
    for k in range(best):
        terms.extend({"topic": k, "rango": r + 1, "palabra": w, "peso": float(p)}
                     for r, (w, p) in enumerate(model.show_topic(k, topn=15)))
        score = np.where(ntok >= 4, np.nan_to_num(theta[:, k]), -1)
        top = np.argpartition(-score, 400)[:400]
        pick = frame.iloc[top].assign(theta=score[top]).sort_values("theta", ascending=False)
        # 20 ejemplos repartidos entre medios para no leer sólo a El Tiempo.
        pick = pick.groupby("source_id", group_keys=False).head(4).head(20)
        examples.extend({"topic": k, "source_id": r.source_id, "government_id": r.government_id,
                         "theta": round(float(r.theta), 3), "title": r.title} for r in pick.itertuples())
    pd.DataFrame(terms).to_csv(out / "topic_terms.csv", index=False)
    pd.DataFrame(examples).to_csv(out / "topic_examples.csv", index=False)
    prevalence = np.nanmean(theta, axis=0)
    pd.DataFrame({"topic": range(best), "prevalencia": prevalence}).to_csv(out / "topic_prevalence.csv", index=False)


def stage_robustness(args, out: Path) -> None:
    """¿Se sostiene el Δ relativo si el modelo se entrena con otra semilla?

    Para cada semilla alternativa se infiere θ sobre todo el corpus y se calcula
    el Δ relativo del tópico emparejado con cada tópico base.
    """
    best = args.k or load_json(out / "train.json")["best_k"]
    frame = _load_prepared(out, ["source_id", "government_id", "month", "tokens"])
    stability = pd.read_csv(out / "topic_stability.csv")
    base_model = LdaModel.load(str(out / "modelos" / f"lda_k{best}.model"))
    bows = [base_model.id2word.doc2bow(t.tolist()) for t in frame["tokens"]]
    keep = np.array([bool(b) for b in bows])
    meta = frame.loc[keep, ["government_id", "month", "source_id"]]
    bows = [b for b in bows if b]
    del frame

    def deltas_for(model, mapping):
        monthly = monthly_shares(doc_topics(model, bows), meta)
        return {t: relative_delta_points(monthly, f"t{m}") for t, m in mapping.items()}

    results = {"base": deltas_for(base_model, {t: t for t in range(best)})}
    for seed in args.stability_seeds:
        logging.info("Robustez: infiriendo con la semilla %s", seed)
        model = LdaModel.load(str(out / "modelos" / f"lda_k{best}_seed{seed}.model"))
        mapping = stability[stability["seed"] == seed].set_index("topic")["matched_topic"].to_dict()
        results[f"semilla_{seed}"] = deltas_for(model, mapping)
    rows = []
    for t in range(best):
        for m in MEDIA:
            row = {"topic": t, "source_id": m}
            row.update({name: float(res[t][m]) for name, res in results.items()})
            rows.append(row)
    table = pd.DataFrame(rows)
    cols = list(results)
    signs = np.sign(table[cols])
    table["mismo_signo"] = signs.nunique(axis=1).eq(1)
    robust = pd.read_csv(out / "topic_robustness.csv").set_index("topic")["robustez"]
    table["robustez"] = table["topic"].map(robust)
    table.to_csv(out / "robustez_deltas.csv", index=False)
    save_json(out / "robustness.json", {
        "pct_mismo_signo_todos": float(100 * table["mismo_signo"].mean()),
        "pct_mismo_signo_por_robustez": (100 * table.groupby("robustez")["mismo_signo"].mean()).round(1).to_dict(),
        "correlacion_base_vs_semillas": {c: float(table["base"].corr(table[c])) for c in cols[1:]},
    })


def _labels(out: Path, k: int) -> dict[int, str]:
    path = HERE / "topic_labels.csv"
    if path.exists():
        labels = pd.read_csv(path)
        return dict(zip(labels["topic"], labels["etiqueta"]))
    return {t: f"T{t}" for t in range(k)}


def stage_compare(args, out: Path) -> None:
    best = args.k or load_json(out / "train.json")["best_k"]
    labels = _labels(out, best)
    robust = pd.read_csv(out / "topic_robustness.csv").set_index("topic")["robustez"].to_dict()
    sign_ok = pd.read_csv(out / "robustez_deltas.csv").set_index(["topic", "source_id"])["mismo_signo"]
    model = LdaModel.load(str(out / "modelos" / f"lda_k{best}.model"))
    theta = np.load(out / "theta.npy")
    assign = pd.read_parquet(out / "document_topics.parquet")
    valid = assign["dominant_topic"].to_numpy() >= 0
    theta, assign = theta[valid], assign[valid].reset_index(drop=True)
    topics = [f"t{k}" for k in range(best)]
    shares = pd.concat([assign[["source_id", "government_id", "month"]], pd.DataFrame(theta, columns=topics)], axis=1)

    cell = shares.groupby(["source_id", "government_id"])[topics].mean()
    cell.to_csv(out / "participacion_medio_gobierno.csv")
    monthly = monthly_shares(theta, assign)
    monthly.to_csv(out / "participacion_mensual.csv")

    rows = []
    for k, t in enumerate(topics):
        # Sólo meses con los 5 medios: así Δ y Δ relativo comparan los mismos meses.
        wide = monthly[t].unstack("source_id")[MEDIA].dropna()
        rel = relative_series(wide)
        for m in MEDIA:
            absolute = block_bootstrap_diff(wide.loc["petro", m], wide.loc["duque", m], seed=args.seed + k)
            relative = block_bootstrap_diff(rel.loc["petro", m], rel.loc["duque", m], seed=args.seed + k)
            rows.append({
                "topic": k, "etiqueta": labels.get(k, f"T{k}"), "robustez": robust[k], "source_id": m,
                "mismo_signo_otras_semillas": bool(sign_ok.loc[(k, m)]),
                "duque": float(cell.loc[(m, "duque"), t]), "petro": float(cell.loc[(m, "petro"), t]),
                "delta_pp": 100 * absolute["delta"], "delta_low_pp": 100 * absolute["low"],
                "delta_high_pp": 100 * absolute["high"], "delta_p": absolute["p"],
                "delta_rel_pp": 100 * relative["delta"], "delta_rel_low_pp": 100 * relative["low"],
                "delta_rel_high_pp": 100 * relative["high"], "delta_rel_p": relative["p"],
            })
    deltas = pd.DataFrame(rows)
    deltas["delta_p_holm"] = holm_adjust(deltas["delta_p"].to_numpy())
    deltas["delta_rel_p_holm"] = holm_adjust(deltas["delta_rel_p"].to_numpy())
    deltas.to_csv(out / "deltas.csv", index=False)
    check = deltas.groupby("topic")["delta_rel_pp"].sum().abs().max()
    if check > 1e-4:  # pp; θ es float32
        raise AssertionError(f"Δ relativo no suma 0 entre medios (máx {check})")

    js_rows = []
    for gov in GOVS:
        for a in MEDIA:
            for b in MEDIA:
                js_rows.append({"gobierno": gov, "a": a, "b": b,
                                "js": float(jensenshannon(cell.loc[(a, gov)], cell.loc[(b, gov)], base=2))})
    for m in MEDIA:
        js_rows.append({"gobierno": "duque→petro", "a": m, "b": m,
                        "js": float(jensenshannon(cell.loc[(m, "duque")], cell.loc[(m, "petro")], base=2))})
    js = pd.DataFrame(js_rows)
    js.to_csv(out / "distancias_js.csv", index=False)

    prevalence = pd.read_csv(out / "topic_prevalence.csv")["prevalencia"].to_numpy()
    figuras.topicos_palabras(model, labels, prevalence, out, robust)
    figuras.mapa_topicos(model.get_topics(), labels, prevalence, out, robust)
    figuras.heatmap_medio_gobierno(cell, labels, out, robust)
    figuras.delta_relativo(deltas, out)
    figuras.distancias_js(js, out)
    figuras.series_topicos(monthly, labels, deltas, out, robust)
    figuras.ejemplo_titular(_load_prepared(out), np.load(out / "theta.npy"), model, labels, out, robust)
    save_json(out / "compare.json", {
        "k": best, "documentos": len(assign),
        "delta_rel_significativos_holm_0_05": int((deltas["delta_rel_p_holm"] < 0.05).sum()),
        "delta_rel_significativos_y_robustos": int(((deltas["delta_rel_p_holm"] < 0.05)
                                                    & deltas["mismo_signo_otras_semillas"]
                                                    & deltas["robustez"].ne("inestable")).sum()),
        "pares_medio_topico": len(deltas),
    })


STAGES = {
    "prepare": stage_prepare, "train": stage_train, "stability": stage_stability,
    "infer": stage_infer, "examples": stage_examples, "robustness": stage_robustness,
    "compare": stage_compare,
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=HERE / "resultados")
    parser.add_argument("--stage", choices=[*STAGES, "all"], default="all")
    parser.add_argument("--per-cell", type=int, default=40_000)
    parser.add_argument("--heldout-per-cell", type=int, default=2_000)
    parser.add_argument("--topics", type=int, nargs="+", default=[10, 15, 20, 25, 30, 40])
    parser.add_argument("--k", type=int, default=None, help="Fijar K en vez del máximo c_v")
    parser.add_argument("--passes", type=int, default=10)
    parser.add_argument("--workers", type=int, default=10)
    parser.add_argument("--no-below", type=int, default=20)
    parser.add_argument("--no-above", type=float, default=0.5)
    parser.add_argument("--keep-n", type=int, default=20_000)
    parser.add_argument("--cv-docs", type=int, default=100_000)
    parser.add_argument("--stability-seeds", type=int, nargs="+", default=[7, 123])
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("gensim").setLevel(logging.WARNING)

    out = args.output.resolve()
    (out / "modelos").mkdir(parents=True, exist_ok=True)
    (out / "figuras").mkdir(exist_ok=True)
    config = {
        "input_sha256": sha256(args.input), "per_cell": args.per_cell, "seed": args.seed,
        "no_below": args.no_below, "no_above": args.no_above, "keep_n": args.keep_n,
        "stopwords_sha256": sha256(HERE / "stopwords_dominio.txt"), "passes": args.passes,
    }
    config_path = out / "config.json"
    if config_path.exists() and load_json(config_path) != config and args.stage not in ("prepare", "all"):
        raise ValueError("Los resultados pertenecen a otro input/configuración; usar otra --output")
    save_json(config_path, config)

    stages = list(STAGES) if args.stage == "all" else [args.stage]
    for name in stages:
        t0 = time.monotonic()
        logging.info("== etapa %s", name)
        STAGES[name](args, out)
        logging.info("== %s terminada en %.0f s", name, time.monotonic() - t0)


if __name__ == "__main__":
    main()
