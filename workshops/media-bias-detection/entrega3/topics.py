"""LDA conjunto Duque + Petro sobre titulares reconstruidos desde el slug.

Etapas (reanudables, cada una lee lo que dejó la anterior en --output):

    prepare    filtra, tokeniza, une bigramas, muestra balanceada, diccionario
    train      grilla de K con LdaMulticore; c_v y perplejidad en held-out
    ensemble   LDA de consenso (EnsembleLda): sólo los tópicos que se repiten
    stability  re-entrena el modelo con otras semillas y empareja tópicos
    infer      distribución de tópicos para los ~1,57 M de titulares
    examples   palabras y titulares de ejemplo para etiquetar cada tópico
    robustness Δ relativo recalculado con los modelos de las otras semillas
    compare    participación por medio y gobierno, Δ y Δ relativo, JS

El modelo se entrena con una muestra balanceada (mismo número de titulares por
medio × gobierno) para que ni El Tiempo (40 % del corpus) ni Petro (+37 % de
titulares) definan los tópicos por volumen; después se infiere sobre todo.

--model elige el modelo: `lda` (grilla, resultados en --output), `ensemble`
(resultados en --output/ensemble) o `bertopic` (lo produce bertopic_topics.py en
--output/bertopic; aquí sólo corre `compare`). Los tres dejan los mismos
artefactos (theta.npy, topic_terms.csv, topic_word.npy…), así que `compare` y
las figuras sirven para todos. --ids restringe el corpus a una lista de
article_id (p. ej. el subcorpus de asuntos públicos).
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
    "published_date", "date_precision", "non_news_reason", "section",
]
# Secciones con menos de este peso dentro de su medio se agrupan en "(otras)"
# al reponderar: con pocos titulares el peso de la celda sería ruido.
MIN_SECTION_SHARE = 0.005
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
    similitud. Si `second` tiene menos tópicos, los que sobran en `first` quedan
    con índice -1 y similitud 0 (el modelo de consenso puede devolver K distintos).
    """
    similarity = topic_similarity(first, second)
    rows, cols = linear_sum_assignment(-similarity)
    matched = np.full(len(first), -1)
    sims = np.zeros(len(first))
    matched[rows] = cols
    sims[rows] = similarity[rows, cols]
    return matched, sims


# Con R réplicas el p-valor bootstrap no baja de 1/R, y Holm lo multiplica por el
# número de pruebas: con 2.000 réplicas y 125 pruebas el mínimo ajustado era 0,0625
# y nada podía ser significativo. 20.000 réplicas dejan el piso en ~0,006.
BOOTSTRAP_REPS = 20_000


def block_bootstrap_diff(after, before, repetitions=BOOTSTRAP_REPS, block_length=3, seed=42) -> dict:
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


def jaccard_words(a, b) -> float:
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if a | b else 0.0


def top_words(topic_word: np.ndarray, vocab: list[str], k: int, n: int = 10) -> list[str]:
    return [vocab[i] for i in np.argsort(-topic_word[k])[:n]]


def robustness_class(jaccard_mean: float) -> str:
    if jaccard_mean >= ROBUSTO:
        return "robusto"
    return "parcial" if jaccard_mean >= PARCIAL else "inestable"


def monthly_shares(theta: np.ndarray, meta: pd.DataFrame, weights: np.ndarray | None = None) -> pd.DataFrame:
    """Media de θ por gobierno × mes × medio (columnas t0..tK), ponderada si hay `weights`."""
    topics = [f"t{k}" for k in range(theta.shape[1])]
    keys = meta[["government_id", "month", "source_id"]].reset_index(drop=True)
    w = np.ones(len(theta)) if weights is None else np.asarray(weights, dtype=float)
    frame = pd.concat([keys, pd.DataFrame(theta * w[:, None], columns=topics), pd.Series(w, name="_w")], axis=1)
    sums = frame.groupby(["government_id", "month", "source_id"])[topics + ["_w"]].sum()
    return sums[topics].div(sums["_w"], axis=0)


def section_weights(meta: pd.DataFrame) -> np.ndarray:
    """Pesos de post-estratificación por sección, dentro de cada medio.

    Cada titular pesa p(sección | medio, ambos gobiernos) / p(sección | medio,
    su gobierno): así los dos gobiernos tienen la misma mezcla de secciones del
    medio. No hace falta armonizar taxonomías entre medios porque la
    comparación es siempre dentro del mismo medio. Lo que queda es el cambio
    *dentro* de las secciones; un cambio real de cuánto cubre el medio una
    sección también se descuenta.
    """
    frame = meta[["source_id", "government_id"]].copy()
    frame["sec"] = meta["section"].fillna("(sin sección)").to_numpy()
    share = frame.groupby(["source_id", "sec"]).size() / frame.groupby("source_id").size()
    rare = share[share < MIN_SECTION_SHARE].index
    frame.loc[pd.MultiIndex.from_frame(frame[["source_id", "sec"]]).isin(rare), "sec"] = "(otras)"
    pooled = frame.groupby(["source_id", "sec"]).size() / frame.groupby("source_id").size()
    by_gov = frame.groupby(["source_id", "government_id", "sec"]).size() / frame.groupby(
        ["source_id", "government_id"]).size()
    idx_pool = pd.MultiIndex.from_frame(frame[["source_id", "sec"]])
    idx_gov = pd.MultiIndex.from_frame(frame[["source_id", "government_id", "sec"]])
    return (pooled.reindex(idx_pool).to_numpy() / by_gov.reindex(idx_gov).to_numpy()).astype(float)


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
    if args.ids:
        ids = pd.read_csv(args.ids)["article_id"]
        frame = frame[frame["article_id"].isin(ids)].reset_index(drop=True)
        funnel.append((args.ids_label, len(frame)))
    del raw

    frame["published_date"] = pd.to_datetime(frame["published_date"])
    frame["month"] = frame["published_date"].dt.to_period("M").dt.to_timestamp()

    logging.info("Tokenizando %s titulares", len(frame))
    nltk_only = {fold(w) for w in stopwords.words("spanish")} - KEEP_WORDS
    stops = stop_words()
    frame["tokens"] = frame["title"].map(partial(tokenize, stop_words=stops))

    sample_idx = balanced_sample(frame, args.per_cell, args.seed)
    frame["in_sample"] = frame.index.isin(sample_idx)
    funnel.append((f"Muestra de entrenamiento ({figuras.miles(args.per_cell)} × 10 celdas)",
                   int(frame["in_sample"].sum())))

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
    probe = frame.sample(min(200_000, len(frame)), random_state=args.seed)
    before = pd.Series([w for t in probe["title"] for w in set(tokenize(t, nltk_only))]).value_counts()
    after = pd.Series([w for t in probe["tokens"] for w in set(t)]).value_counts()
    removed = set(before.index) - set(after.index)
    bigrams = [w for w in after.index if "_" in w][:15]
    figuras.tokens_antes_despues(before.head(20), after.head(20), removed, bigrams, len(probe), out)

    keep = [
        "article_id", "url", "source_id", "government_id", "title", "published_date", "month",
        "date_precision", "section", "tokens", "in_sample", "in_heldout",
    ]
    frame[keep].to_parquet(out / "prepared.parquet", index=False)

    cells = frame.groupby(["source_id", "government_id"]).size().rename("disponibles").reset_index()
    cells.to_csv(out / "celdas.csv", index=False)
    monthly = frame.groupby(["source_id", "month"]).size().rename("titulares").reset_index()
    monthly.to_csv(out / "volumen_mensual.csv", index=False)

    figuras.embudo(funnel, out)
    figuras.volumen_mensual(monthly, out)
    figuras.muestra_balanceada(cells, args.per_cell, out)
    if args.ids:
        figuras.subcorpus(cells, pd.read_csv(out.parent / "resultados" / "celdas.csv")
                          if (out.parent / "resultados" / "celdas.csv").exists() else None, out)

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


def _results_dir(args, out: Path) -> Path:
    """Los modelos alternativos escriben en su propia subcarpeta; el LDA de grilla en --output."""
    res = out if args.model == "lda" else out / args.model
    (res / "figuras").mkdir(parents=True, exist_ok=True)
    return res


def _model_path(args, out: Path, seed: int | None = None) -> Path:
    seed = args.seed if seed is None else seed
    if args.model == "ensemble":
        return out / "modelos" / f"ensemble_seed{seed}_eps{args.ensemble_eps}.model"
    best = args.k or load_json(out / "train.json")["best_k"]
    suffix = "" if seed == args.seed else f"_seed{seed}"
    return out / "modelos" / f"lda_k{best}{suffix}.model"


def _sample_bows(out: Path):
    frame = _load_prepared(out, ["tokens", "in_sample"])
    dictionary = Dictionary.load(str(out / "modelos" / "dictionary.dict"))
    texts = [t.tolist() for t in frame.loc[frame["in_sample"], "tokens"]]
    pairs = [(dictionary.doc2bow(t), t) for t in texts]
    pairs = [(b, t) for b, t in pairs if b]
    return dictionary, [b for b, _ in pairs], [t for _, t in pairs]


def stage_ensemble(args, out: Path) -> None:
    """LDA de consenso: entrena `--ensemble-models` LDA y conserva sólo los
    tópicos que aparecen en varios de ellos (clustering de tópicos con DBSCAN
    sobre distancias coseno). Se repite con las semillas de estabilidad para
    medir si el consenso, a su vez, es reproducible."""
    from gensim.models import EnsembleLda

    dictionary, bows, texts = _sample_bows(out)
    rows, grid = [], []
    for seed in [args.seed, *args.stability_seeds]:
        elda_path = out / "modelos" / f"ensemble_seed{seed}.elda"
        t0 = time.monotonic()
        if elda_path.exists():
            elda = EnsembleLda.load(str(elda_path))
        else:
            logging.info("EnsembleLda semilla %s: %s modelos de K=%s", seed, args.ensemble_models, args.ensemble_topics)
            elda = EnsembleLda(
                corpus=bows, id2word=dictionary, num_topics=args.ensemble_topics,
                num_models=args.ensemble_models, passes=args.passes, iterations=100,
                random_state=seed, topic_model_class="lda", ensemble_workers=args.workers,
                distance_workers=args.workers,
            )
            elda.save(str(elda_path))
        # Cuántos tópicos sobreviven según el radio del clustering (eps, distancia coseno).
        for eps in (0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35):
            elda.recluster(eps=eps)
            grid.append({"seed": seed, "eps": eps, "topicos_estables": len(elda.get_topics())})
        elda.recluster(eps=args.ensemble_eps)
        model = elda.generate_gensim_representation()
        if model is None or model.num_topics < 2:
            raise RuntimeError(f"El consenso de la semilla {seed} no dejó tópicos estables con eps={args.ensemble_eps}")
        model.save(str(_model_path(args, out, seed)))
        rows.append({"seed": seed, "eps": args.ensemble_eps, "topicos_estables": model.num_topics,
                     "topicos_entrenados": args.ensemble_models * args.ensemble_topics,
                     "segundos": round(time.monotonic() - t0, 1)})
        logging.info("Semilla %s, eps %s: %s tópicos estables", seed, args.ensemble_eps, model.num_topics)
    res = _results_dir(args, out)
    model = LdaModel.load(str(_model_path(args, out)))
    rng = np.random.default_rng(args.seed)
    cv_texts = [texts[i] for i in rng.choice(len(texts), size=min(args.cv_docs, len(texts)), replace=False)]
    cv = CoherenceModel(model=model, texts=cv_texts, dictionary=dictionary, coherence="c_v",
                        topn=10, processes=args.workers).get_coherence()
    pd.DataFrame(grid).to_csv(res / "ensemble_eps.csv", index=False)
    save_json(res / "ensemble.json", {
        "k": model.num_topics, "coherence_cv": float(cv), "eps": args.ensemble_eps,
        "modelos_por_ensamble": args.ensemble_models, "k_por_modelo": args.ensemble_topics, "entrenamiento": rows,
    })


def stage_stability(args, out: Path) -> None:
    res = _results_dir(args, out)
    dictionary, bows, _ = _sample_bows(out)
    vocab = [dictionary[i] for i in range(len(dictionary))]
    base = LdaModel.load(str(_model_path(args, out))).get_topics()
    rows, matrices, jaccards = [], {}, {}
    for seed in args.stability_seeds:
        path = _model_path(args, out, seed)
        if path.exists():
            other = LdaModel.load(str(path))
        elif args.model == "lda":
            logging.info("Estabilidad: semilla %s", seed)
            other = _train_one(bows, dictionary, base.shape[0], seed, args)
            other.save(str(path))
        else:
            raise FileNotFoundError(f"{path}: correr antes la etapa ensemble")
        rows += stability_rows(base, other.get_topics(), vocab, seed, matrices, jaccards)
    save_stability(rows, matrices, jaccards, args.stability_seeds, res)


def stability_rows(base, other, vocab, seed, matrices, jaccards) -> list[dict]:
    """Empareja los tópicos de `other` con los de `base` y mide su parecido."""
    matched, sims = match_topics(base, other)
    pad = np.vstack([other, np.zeros((1, other.shape[1]))])  # fila nula para los no emparejados
    matrices[seed] = topic_similarity(base, pad[matched])
    jac = np.array([jaccard_words(top_words(base, vocab, t), top_words(other, vocab, m)) if m >= 0 else 0.0
                    for t, m in enumerate(matched)])
    jaccards[seed] = jac
    return [{"topic": t, "seed": seed, "matched_topic": int(m), "similitud_js": float(sm), "jaccard_top10": float(j)}
            for t, (m, sm, j) in enumerate(zip(matched, sims, jac))]


def save_stability(rows, matrices, jaccards, seeds, res: Path) -> None:
    table = pd.DataFrame(rows)
    table.to_csv(res / "topic_stability.csv", index=False)
    robust = table.groupby("topic").agg(jaccard_medio=("jaccard_top10", "mean"),
                                        similitud_js_min=("similitud_js", "min"))
    robust["robustez"] = robust["jaccard_medio"].map(robustness_class)
    robust.to_csv(res / "topic_robustness.csv")
    save_json(res / "stability.json", {
        "k": len(robust), "seeds": seeds,
        "criterio": f"Jaccard medio de las 10 palabras principales: robusto ≥ {ROBUSTO}, parcial ≥ {PARCIAL}",
        "conteo": robust["robustez"].value_counts().to_dict(),
        "jaccard_medio_global": float(robust["jaccard_medio"].mean()),
        "similitud_js_media": float(table["similitud_js"].mean()),
    })
    figuras.estabilidad(matrices, jaccards, res)


def stage_infer(args, out: Path) -> None:
    res = _results_dir(args, out)
    model = LdaModel.load(str(_model_path(args, out)))
    frame = _load_prepared(out, ["article_id", "source_id", "government_id", "month", "tokens"])
    dictionary = model.id2word
    bows = [dictionary.doc2bow(t.tolist()) for t in frame["tokens"]]
    empty = np.array([not b for b in bows])
    logging.info("Infiriendo %s titulares (%s sin vocabulario)", len(bows), empty.sum())
    theta = doc_topics(model, bows)
    theta[empty] = np.nan
    np.save(res / "theta.npy", theta)
    assign = save_assignments(frame, theta, empty, res)
    figuras.confianza(assign[assign["dominant_topic"] >= 0], res)

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
    pyLDAvis.save_html(vis, str(res / "lda_visualization.html"))


def save_assignments(frame: pd.DataFrame, theta: np.ndarray, empty: np.ndarray, res: Path) -> pd.DataFrame:
    assign = frame[["article_id", "source_id", "government_id", "month"]].copy()
    filled = np.nan_to_num(theta)
    assign["dominant_topic"] = np.where(empty, -1, filled.argmax(axis=1))
    assign["topic_confidence"] = np.where(empty, 0.0, filled.max(axis=1))
    assign.to_parquet(res / "document_topics.parquet", index=False)
    conf = assign[assign["dominant_topic"] >= 0]
    table = conf.groupby("source_id")["topic_confidence"].describe(percentiles=[0.25, 0.5, 0.75])
    table["pct_menor_0_3"] = conf.groupby("source_id")["topic_confidence"].apply(lambda s: 100 * (s < 0.3).mean())
    table["sin_vocabulario"] = assign.groupby("source_id")["dominant_topic"].apply(lambda s: int((s < 0).sum()))
    table.to_csv(res / "topic_confidence.csv")
    save_json(res / "infer.json", {
        "k": int(theta.shape[1]), "documentos": len(assign), "sin_vocabulario": int(empty.sum()),
        "confianza_media": float(conf["topic_confidence"].mean()),
        "pct_confianza_menor_0_3": float(100 * (conf["topic_confidence"] < 0.3).mean()),
    })
    return assign


def stage_examples(args, out: Path) -> None:
    res = _results_dir(args, out)
    model = LdaModel.load(str(_model_path(args, out)))
    topic_word = model.get_topics()
    vocab = [model.id2word[i] for i in range(len(model.id2word))]
    frame = _load_prepared(out, ["article_id", "source_id", "government_id", "title", "tokens"])
    save_examples(frame, np.load(res / "theta.npy"), topic_word, vocab, res)


def save_examples(frame: pd.DataFrame, theta: np.ndarray, topic_word: np.ndarray, vocab: list[str],
                  res: Path) -> None:
    """Palabras, matriz tópico-palabra, prevalencia y 20 titulares de ejemplo por tópico."""
    ntok = frame["tokens"].map(len).to_numpy()
    terms, examples = [], []
    for k in range(topic_word.shape[0]):
        order = np.argsort(-topic_word[k])[:15]
        terms.extend({"topic": k, "rango": r + 1, "palabra": vocab[i], "peso": float(topic_word[k, i])}
                     for r, i in enumerate(order))
        score = np.where(ntok >= 4, np.nan_to_num(theta[:, k]), -1)
        top = np.argpartition(-score, 400)[:400]
        pick = frame.iloc[top].assign(theta=score[top]).sort_values("theta", ascending=False)
        # 20 ejemplos repartidos entre medios para no leer sólo a El Tiempo.
        pick = pick.groupby("source_id", group_keys=False).head(4).head(20)
        examples.extend({"topic": k, "source_id": r.source_id, "government_id": r.government_id,
                         "theta": round(float(r.theta), 3), "title": r.title} for r in pick.itertuples())
    pd.DataFrame(terms).to_csv(res / "topic_terms.csv", index=False)
    pd.DataFrame(examples).to_csv(res / "topic_examples.csv", index=False)
    np.save(res / "topic_word.npy", topic_word.astype(np.float32))
    prevalence = np.nanmean(theta, axis=0)
    pd.DataFrame({"topic": range(len(prevalence)), "prevalencia": prevalence}).to_csv(
        res / "topic_prevalence.csv", index=False)


def stage_robustness(args, out: Path) -> None:
    """¿Se sostiene el Δ relativo si el modelo se entrena con otra semilla?

    Para cada semilla alternativa se infiere θ sobre todo el corpus y se calcula
    el Δ relativo del tópico emparejado con cada tópico base.
    """
    res = _results_dir(args, out)
    frame = _load_prepared(out, ["source_id", "government_id", "month", "tokens"])
    stability = pd.read_csv(res / "topic_stability.csv")
    base_model = LdaModel.load(str(_model_path(args, out)))
    bows = [base_model.id2word.doc2bow(t.tolist()) for t in frame["tokens"]]
    keep = np.array([bool(b) for b in bows])
    meta = frame.loc[keep, ["government_id", "month", "source_id"]]
    bows = [b for b in bows if b]
    del frame

    thetas = {"base": doc_topics(base_model, bows)}
    for seed in args.stability_seeds:
        logging.info("Robustez: infiriendo con la semilla %s", seed)
        thetas[f"semilla_{seed}"] = doc_topics(LdaModel.load(str(_model_path(args, out, seed))), bows)
    save_robustness(thetas, meta, stability, args.stability_seeds, res)


def save_robustness(thetas: dict, meta: pd.DataFrame, stability: pd.DataFrame, seeds, res: Path) -> None:
    k = thetas["base"].shape[1]
    results = {}
    for name, theta in thetas.items():
        monthly = monthly_shares(theta, meta)
        if name == "base":
            mapping = {t: t for t in range(k)}
        else:
            seed = int(name.split("_")[1])
            mapping = stability[stability["seed"] == seed].set_index("topic")["matched_topic"].to_dict()
        results[name] = {t: (relative_delta_points(monthly, f"t{m}") if m >= 0 else None) for t, m in mapping.items()}
    rows = []
    for t in range(k):
        for m in MEDIA:
            row = {"topic": t, "source_id": m}
            row.update({name: (float(res_[t][m]) if res_[t] is not None else np.nan) for name, res_ in results.items()})
            rows.append(row)
    table = pd.DataFrame(rows)
    cols = list(results)
    signs = np.sign(table[cols])
    table["mismo_signo"] = signs.notna().all(axis=1) & signs.nunique(axis=1).eq(1)
    robust = pd.read_csv(res / "topic_robustness.csv").set_index("topic")["robustez"]
    table["robustez"] = table["topic"].map(robust)
    table.to_csv(res / "robustez_deltas.csv", index=False)
    save_json(res / "robustness.json", {
        "pct_mismo_signo_todos": float(100 * table["mismo_signo"].mean()),
        "pct_mismo_signo_por_robustez": (100 * table.groupby("robustez")["mismo_signo"].mean()).round(1).to_dict(),
        "correlacion_base_vs_semillas": {c: float(table["base"].corr(table[c])) for c in cols[1:]},
    })


def _labels(args, k: int) -> dict[int, str]:
    path = args.labels
    if path and Path(path).exists():
        labels = pd.read_csv(path)
        return dict(zip(labels["topic"], labels["etiqueta"]))
    return {t: f"T{t}" for t in range(k)}


def _delta_rows(monthly, cell, topics, labels, robust, sign_ok, seed, prefix=""):
    rows = []
    for k, t in enumerate(topics):
        # Sólo meses con los 5 medios: así Δ y Δ relativo comparan los mismos meses.
        wide = monthly[t].unstack("source_id")[MEDIA].dropna()
        rel = relative_series(wide)
        for m in MEDIA:
            absolute = block_bootstrap_diff(wide.loc["petro", m], wide.loc["duque", m], seed=seed + k)
            relative = block_bootstrap_diff(rel.loc["petro", m], rel.loc["duque", m], seed=seed + k)
            rows.append({
                "topic": k, "etiqueta": labels.get(k, f"T{k}"), "robustez": robust[k], "source_id": m,
                "mismo_signo_otras_semillas": bool(sign_ok.loc[(k, m)]),
                f"{prefix}duque": float(cell.loc[(m, "duque"), t]), f"{prefix}petro": float(cell.loc[(m, "petro"), t]),
                f"{prefix}delta_pp": 100 * absolute["delta"], f"{prefix}delta_low_pp": 100 * absolute["low"],
                f"{prefix}delta_high_pp": 100 * absolute["high"], f"{prefix}delta_p": absolute["p"],
                f"{prefix}delta_rel_pp": 100 * relative["delta"], f"{prefix}delta_rel_low_pp": 100 * relative["low"],
                f"{prefix}delta_rel_high_pp": 100 * relative["high"], f"{prefix}delta_rel_p": relative["p"],
            })
    deltas = pd.DataFrame(rows)
    deltas[f"{prefix}delta_p_holm"] = holm_adjust(deltas[f"{prefix}delta_p"].to_numpy())
    deltas[f"{prefix}delta_rel_p_holm"] = holm_adjust(deltas[f"{prefix}delta_rel_p"].to_numpy())
    check = deltas.groupby("topic")[f"{prefix}delta_rel_pp"].sum().abs().max()
    if check > 1e-4:  # pp; θ es float32
        raise AssertionError(f"Δ relativo no suma 0 entre medios (máx {check})")
    return deltas


def stage_compare(args, out: Path) -> None:
    res = _results_dir(args, out)
    theta = np.load(res / "theta.npy")
    k_topics = theta.shape[1]
    labels = _labels(args, k_topics)
    robust = pd.read_csv(res / "topic_robustness.csv").set_index("topic")["robustez"].to_dict()
    sign_ok = pd.read_csv(res / "robustez_deltas.csv").set_index(["topic", "source_id"])["mismo_signo"]
    assign = pd.read_parquet(res / "document_topics.parquet")
    sections = _load_prepared(out, ["section"])["section"]
    valid = assign["dominant_topic"].to_numpy() >= 0
    theta = theta[valid]
    assign = assign[valid].reset_index(drop=True).assign(section=sections[valid].to_numpy())
    topics = [f"t{k}" for k in range(k_topics)]
    weights = section_weights(assign)

    def cell_shares(w):
        frame = pd.concat([assign[["source_id", "government_id"]], pd.DataFrame(theta * w[:, None], columns=topics),
                           pd.Series(w, name="_w")], axis=1)
        sums = frame.groupby(["source_id", "government_id"])[topics + ["_w"]].sum()
        return sums[topics].div(sums["_w"], axis=0)

    cell = cell_shares(np.ones(len(theta)))
    cell.to_csv(res / "participacion_medio_gobierno.csv")
    monthly = monthly_shares(theta, assign)
    monthly.to_csv(res / "participacion_mensual.csv")
    cell_sec = cell_shares(weights)
    monthly_sec = monthly_shares(theta, assign, weights)

    deltas = _delta_rows(monthly, cell, topics, labels, robust, sign_ok, args.seed)
    sec = _delta_rows(monthly_sec, cell_sec, topics, labels, robust, sign_ok, args.seed, prefix="secc_")
    deltas = deltas.merge(sec[[c for c in sec.columns if c.startswith("secc_")] + ["topic", "source_id"]],
                          on=["topic", "source_id"])
    deltas.to_csv(res / "deltas.csv", index=False)

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
    js.to_csv(res / "distancias_js.csv", index=False)

    terms = pd.read_csv(res / "topic_terms.csv")
    topic_word = np.load(res / "topic_word.npy")
    prevalence = pd.read_csv(res / "topic_prevalence.csv")["prevalencia"].to_numpy()
    figuras.topicos_palabras(terms, labels, prevalence, res, robust)
    figuras.mapa_topicos(topic_word, labels, prevalence, res, robust)
    figuras.heatmap_medio_gobierno(cell, labels, res, robust)
    figuras.delta_relativo(deltas, res)
    figuras.distancias_js(js, res)
    figuras.series_topicos(monthly, labels, deltas, res, robust)
    figuras.control_seccion(deltas, res)
    if args.model != "bertopic":
        model = LdaModel.load(str(_model_path(args, out)))
        figuras.ejemplo_titular(_load_prepared(out), np.load(res / "theta.npy"), model, labels, res, robust)
    fiables = deltas["robustez"].ne("inestable") & deltas["mismo_signo_otras_semillas"]
    save_json(res / "compare.json", {
        "k": k_topics, "documentos": len(assign),
        "delta_rel_significativos_holm_0_05": int((deltas["delta_rel_p_holm"] < 0.05).sum()),
        "delta_rel_significativos_y_robustos": int(((deltas["delta_rel_p_holm"] < 0.05) & fiables).sum()),
        "secc_delta_rel_significativos_y_robustos": int(((deltas["secc_delta_rel_p_holm"] < 0.05) & fiables).sum()),
        "pares_medio_topico": len(deltas),
        "bootstrap_reps": BOOTSTRAP_REPS,
        "p_min_ajustado_holm": len(deltas) / BOOTSTRAP_REPS,
    })


STAGES = {
    "prepare": stage_prepare, "train": stage_train, "ensemble": stage_ensemble, "stability": stage_stability,
    "infer": stage_infer, "examples": stage_examples, "robustness": stage_robustness,
    "compare": stage_compare,
}
PIPELINES = {
    "lda": ["prepare", "train", "stability", "infer", "examples", "robustness", "compare"],
    "ensemble": ["ensemble", "stability", "infer", "examples", "robustness", "compare"],
    "bertopic": ["compare"],
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=HERE / "resultados")
    parser.add_argument("--stage", choices=[*STAGES, "all"], default="all")
    parser.add_argument("--model", choices=list(PIPELINES), default="lda")
    parser.add_argument("--labels", type=Path, default=HERE / "topic_labels.csv")
    parser.add_argument("--ids", type=Path, default=None, help="CSV con article_id para restringir el corpus")
    parser.add_argument("--ids-label", default="Subcorpus (--ids)")
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
    parser.add_argument("--ensemble-models", type=int, default=16)
    parser.add_argument("--ensemble-topics", type=int, default=20)
    parser.add_argument("--ensemble-eps", type=float, default=0.1,
                        help="Radio (distancia coseno) para agrupar tópicos en el consenso")
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
    if args.ids:
        config["ids_sha256"] = sha256(args.ids)
    config_path = out / "config.json"
    if config_path.exists() and load_json(config_path) != config and args.stage not in ("prepare", "all"):
        raise ValueError("Los resultados pertenecen a otro input/configuración; usar otra --output")
    save_json(config_path, config)

    stages = PIPELINES[args.model] if args.stage == "all" else [args.stage]
    for name in stages:
        t0 = time.monotonic()
        logging.info("== etapa %s (%s)", name, args.model)
        STAGES[name](args, out)
        logging.info("== %s terminada en %.0f s", name, time.monotonic() - t0)


if __name__ == "__main__":
    main()
