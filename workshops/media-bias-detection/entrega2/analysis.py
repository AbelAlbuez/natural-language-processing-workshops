import argparse
import hashlib
import importlib.metadata
import json
import logging
import time
from collections import Counter
from functools import partial
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from gensim.corpora import Dictionary, MmCorpus
from gensim.models import CoherenceModel, LdaModel
from nltk.corpus import stopwords
from scipy.stats import linregress, pearsonr
from sklearn.feature_extraction.text import CountVectorizer

from core import counter_metrics, fold, keyword_pattern, msttr, ngrams, normalize, tokenize, ttr, yules_k


TOPICS = {
    "Reforma tributaria": ["reforma tributaria", "impuesto", "impuestos", "recaudo", "reforma fiscal"],
    "Conflicto armado": ["conflicto armado", "guerrilla", "guerrillas", "eln", "farc", "disidencias", "violencia"],
    "Corrupcion": ["corrupcion", "fraude", "peculado", "soborno", "odebrecht", "lavado de dinero"],
}
CASES = {
    "Reforma y paro 2021": ("2021-04-15", "2021-06-16", ["reforma tributaria", "solidaridad sostenible", "paro nacional"]),
    "Bombardeo y menores 2019": ("2019-11-01", "2019-11-16", ["bombardeo", "menores", "san vicente del caguan"]),
    "Centros Poblados 2021": ("2021-08-01", "2021-10-01", ["centros poblados", "mintic", "abudinen", "emilio tapia"]),
}
CUSTOM_STOPS = {fold(word) for word in ["dice", "dijo", "senalo", "indico", "expreso", "luego", "posteriormente", "ayer", "hoy", "manana"]}


def save_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(partial(stream.read, 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def finite_number(value):
    return float(value) if np.isfinite(value) else None


def save_figure(output, filename):
    plt.tight_layout()
    plt.savefig(output / "figuras" / filename, dpi=150, bbox_inches="tight")
    plt.close()


def load_data(path):
    columns = ["article_id", "source_id", "title", "url", "published_date", "date_precision", "title_source", "government_id", "content_chars"]
    frame = pd.read_parquet(path, columns=columns)
    if frame.empty or not frame["article_id"].is_unique:
        raise ValueError("Corpus vacio o IDs duplicados")
    frame["published_date"] = pd.to_datetime(frame["published_date"], errors="raise")
    if not frame["published_date"].between("2018-08-07", "2022-08-06").all():
        raise ValueError("El export contiene fechas fuera del corte Duque")
    frame["year"] = frame["published_date"].dt.year
    frame["title_norm"] = frame["title"].map(normalize)
    stop_words = {fold(word) for word in stopwords.words("spanish")} | CUSTOM_STOPS
    frame["tokens"] = frame["title"].map(partial(tokenize, stop_words=stop_words))
    frame["num_tokens"] = frame["tokens"].map(len)
    return frame, sorted(stop_words)


def corpus_profile(frame, output):
    profile = frame.groupby("source_id").agg(
        articulos=("article_id", "size"), con_titulo=("title", "count"),
        desde=("published_date", "min"), hasta=("published_date", "max"),
        tokens_promedio=("num_tokens", "mean"),
    )
    profile["sin_titulo"] = profile["articulos"] - profile["con_titulo"]
    profile["pct_titulo"] = 100 * profile["con_titulo"] / profile["articulos"]
    profile.to_csv(output / "cobertura_corpus.csv")
    frame.groupby(["source_id", "year", "date_precision"]).size().rename("articulos").to_csv(output / "cobertura_temporal.csv")
    frame.groupby(["source_id", "date_precision", "government_id"], dropna=False).size().rename("articulos").to_csv(output / "precision_gobierno.csv")
    profile["articulos"].sort_values().plot.barh(figsize=(9, 4), color="#237c69")
    plt.title("Candidatos Duque: representacion desigual de los medios")
    plt.xlabel("Articulos del export")
    save_figure(output, "cobertura_corpus.png")
    return {
        "articulos": len(frame), "medios": len(profile), "con_titulo": int(frame["title"].notna().sum()),
        "sin_titulo": int(frame["title"].isna().sum()), "tokens_vacios": int(frame["num_tokens"].eq(0).sum()),
        "titulo_source": frame["title_source"].fillna("ausente").value_counts().to_dict(),
        "date_precision": frame["date_precision"].value_counts().to_dict(),
        "con_cuerpo": int(frame["content_chars"].gt(0).sum()),
        "desde": frame["published_date"].min().date().isoformat(),
        "hasta": frame["published_date"].max().date().isoformat(),
    }


def textometry(frame, output):
    frequencies = Counter()
    for tokens in frame["tokens"]:
        frequencies.update(tokens)
    words = pd.DataFrame(frequencies.most_common(), columns=["palabra", "frecuencia"])
    words["rango"] = np.arange(1, len(words) + 1)
    words.to_csv(output / "frecuencias.csv", index=False)
    log_ranks = np.log(words["rango"])
    log_frequencies = np.log(words["frecuencia"])
    correlation = pearsonr(log_ranks, log_frequencies)
    fit_mask = words["rango"].between(10, 10000) & words["frecuencia"].gt(1)
    if fit_mask.sum() < 2:
        fit_mask = words["frecuencia"].gt(1)
    regression = linregress(log_ranks[fit_mask], log_frequencies[fit_mask])
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    axes[0].plot(words["rango"].iloc[:100], words["frecuencia"].iloc[:100], color="#237c69")
    axes[0].set(title="Frecuencias: primeros 100 rangos", xlabel="Rango", ylabel="Frecuencia")
    axes[1].loglog(words["rango"], words["frecuencia"], ".", color="#b8474b", markersize=2)
    axes[1].loglog(words.loc[fit_mask, "rango"], np.exp(regression.intercept) * words.loc[fit_mask, "rango"] ** regression.slope, color="#237c69", label="Ajuste descriptivo")
    axes[1].set(title="Rango-frecuencia log-log", xlabel="Rango", ylabel="Frecuencia")
    axes[1].legend()
    save_figure(output, "zipf_law.png")
    for metric, function in [("ttr", ttr), ("msttr_titulo", msttr), ("yule_k", yules_k)]:
        frame[metric] = frame["tokens"].map(function)
    rows = []
    for medium, subset in frame.groupby("source_id", sort=True):
        counter = Counter()
        concatenated = []
        for tokens in subset["tokens"]:
            counter.update(tokens)
            concatenated.extend(tokens)
        eligible = subset.loc[subset["num_tokens"].gt(0)]
        rows.append({
            "source_id": medium, **counter_metrics(counter), "msttr_50_agregado": msttr(concatenated),
            "ttr_titulo_media": float(eligible["ttr"].mean()),
            "yule_k_titulo_media": float(eligible["yule_k"].mean()),
            "tokens_titulo_media": float(eligible["num_tokens"].mean()),
            "documentos_utiles": len(eligible),
        })
    diversity = pd.DataFrame(rows).set_index("source_id")
    diversity.to_csv(output / "diversidad_por_medio.csv")
    frame[["article_id", "source_id", "num_tokens", "ttr", "msttr_titulo", "yule_k"]].to_parquet(output / "diversidad_documentos.parquet", index=False)
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    sns.boxplot(data=frame.loc[frame["num_tokens"].gt(0)], x="source_id", y="ttr", ax=axes[0], showfliers=False)
    axes[0].set(title="TTR por titulo (depende de longitud)", xlabel="", ylabel="TTR")
    diversity["msttr_50_agregado"].plot.bar(ax=axes[1], color="#237c69", title="MSTTR agregado, ventana 50")
    diversity["yule_k_agregado"].plot.bar(ax=axes[2], color="#b8474b", title="Yule K agregado")
    for axis in axes:
        axis.tick_params(axis="x", rotation=75)
    save_figure(output, "lexical_diversity.png")
    fig, axes = plt.subplots(1, 2, figsize=(13, 6))
    for size, maximum, minimum, name, axis in [(2, 100, 5, "bigrams_top100", axes[0]), (3, 50, 3, "trigrams_top50", axes[1])]:
        vectorizer = CountVectorizer(analyzer=partial(ngrams, size=size), max_features=maximum, min_df=minimum)
        matrix = vectorizer.fit_transform(frame["tokens"])
        counts = np.asarray(matrix.sum(axis=0)).ravel()
        table = pd.DataFrame({"ngram": vectorizer.get_feature_names_out(), "frecuencia": counts, "documentos": np.asarray((matrix > 0).sum(axis=0)).ravel()}).sort_values("frecuencia", ascending=False)
        table.to_csv(output / f"{name}.csv", index=False)
        table.head(15).iloc[::-1].plot.barh(x="ngram", y="frecuencia", legend=False, ax=axis, color="#237c69" if size == 2 else "#b8474b")
        axis.set_title(f"{size}-gramas de tokens depurados")
        del matrix
    save_figure(output, "ngrams.png")
    return {
        **counter_metrics(frequencies), "zipf_pearson_r": finite_number(correlation.statistic),
        "zipf_p": finite_number(correlation.pvalue), "zipf_slope": finite_number(regression.slope),
        "zipf_r2": finite_number(regression.rvalue ** 2), "zipf_rangos_ajustados": int(fit_mask.sum()),
    }


def event_analysis(frame, output):
    denominators = frame.loc[frame["title"].notna()].groupby("source_id").size()
    stats = []
    lexical = []
    for topic, keywords in TOPICS.items():
        subset = frame.loc[frame["title_norm"].str.contains(keyword_pattern(keywords), regex=True)]
        counters = {}
        for medium, documents in subset.groupby("source_id"):
            counter = Counter()
            for tokens in documents["tokens"]:
                counter.update(tokens)
            counters[medium] = counter
        all_words = sum(counters.values(), Counter())
        for medium, denominator in denominators.items():
            documents = subset.loc[subset["source_id"].eq(medium)]
            stats.append({"tema": topic, "source_id": medium, "articulos": len(documents), "denominador_titulos": int(denominator), "pct_medio": 100 * len(documents) / denominator})
            counter = counters.get(medium, Counter())
            rest = all_words - counter
            total = sum(counter.values())
            other_total = sum(rest.values())
            excluded = {word for keyword in keywords for word in normalize(keyword).split()}
            candidates = []
            for word, count in counter.items():
                if count < 3 or all_words[word] < 10 or word in excluded or not other_total:
                    continue
                odds = np.log((count + 0.5) / (total - count + 0.5)) - np.log((rest[word] + 0.5) / (other_total - rest[word] + 0.5))
                candidates.append({"tema": topic, "source_id": medium, "palabra": word, "frecuencia": count, "log_odds_descriptivo": float(odds)})
            lexical.extend(sorted(candidates, key=lambda item: item["log_odds_descriptivo"], reverse=True)[:10])
    stats = pd.DataFrame(stats)
    stats.to_csv(output / "eventos_polemicos.csv", index=False)
    pd.DataFrame(lexical).to_csv(output / "contrastes_lexicos.csv", index=False)
    fig, axes = plt.subplots(1, 3, figsize=(14, 4), sharey=True)
    for axis, (topic, group) in zip(axes, stats.groupby("tema", sort=True)):
        group.sort_values("pct_medio").plot.barh(x="source_id", y="pct_medio", ax=axis, legend=False, color="#237c69")
        axis.set(title=topic, xlabel="% de titulos del medio", ylabel="")
    save_figure(output, "eventos_framing.png")
    case_rows = []
    examples = []
    for case, (start, end, keywords) in CASES.items():
        window = frame.loc[frame["published_date"].ge(start) & frame["published_date"].lt(end)]
        selected = window.loc[window["title_norm"].str.contains(keyword_pattern(keywords))]
        for medium in sorted(frame["source_id"].unique()):
            denominator = int((window["source_id"].eq(medium) & window["title"].notna()).sum())
            documents = selected.loc[selected["source_id"].eq(medium)]
            case_rows.append({"caso": case, "source_id": medium, "articulos": len(documents), "titulos_ventana": denominator, "pct_ventana": 100 * len(documents) / denominator if denominator else np.nan})
            for _, record in documents.sort_values(["published_date", "article_id"]).head(3).iterrows():
                examples.append({"caso": case, "article_id": int(record["article_id"]), "source_id": medium, "fecha": record["published_date"].date().isoformat(), "date_precision": record["date_precision"], "title_source": record["title_source"], "title": record["title"], "url": record["url"]})
    pd.DataFrame(case_rows).to_csv(output / "casos_temporales.csv", index=False)
    pd.DataFrame(examples).to_csv(output / "ejemplos_casos.csv", index=False)
    return stats.groupby("tema")["articulos"].sum().astype(int).to_dict()


def train_lda(frame, output, args):
    models_dir = output / "modelos"
    models_dir.mkdir(exist_ok=True)
    dictionary = Dictionary(frame["tokens"])
    dictionary.filter_extremes(no_below=args.no_below, no_above=0.7, keep_n=10000)
    if len(dictionary) < 2:
        raise ValueError("Vocabulario LDA insuficiente")
    dictionary.save(str(models_dir / "duque_dictionary.dict"))
    indices = []
    bows = []
    texts = []
    for position, tokens in enumerate(frame["tokens"]):
        bow = dictionary.doc2bow(tokens)
        if bow:
            indices.append(position)
            bows.append(bow)
            texts.append(tokens)
    MmCorpus.serialize(str(models_dir / "duque_corpus.mm"), bows)
    corpus = MmCorpus(str(models_dir / "duque_corpus.mm"))
    del bows
    models = []
    for topics in args.topics:
        path = models_dir / f"lda_k{topics}.model"
        start = time.monotonic()
        if path.exists():
            logging.info("Cargando checkpoint K=%s", topics)
            model = LdaModel.load(str(path))
        else:
            logging.info("Entrenando K=%s, documentos=%s, pasadas=%s", topics, len(corpus), args.passes)
            model = LdaModel(
                corpus=corpus, id2word=dictionary, num_topics=topics, random_state=42,
                passes=args.passes, iterations=50, chunksize=2000, eval_every=None,
                per_word_topics=True, minimum_probability=0.0,
            )
            model.save(str(path))
        logging.info("K=%s terminado en %.1f segundos", topics, time.monotonic() - start)
        models.append(model)
    metrics_path = output / "lda_optimization.csv"
    if metrics_path.exists():
        metrics = pd.read_csv(metrics_path)
    else:
        logging.info("Coherencia c_v sobre todos los documentos utiles, procesos=1")
        estimator = CoherenceModel.for_models(models, dictionary=dictionary, texts=texts, coherence="c_v", topn=min(20, len(dictionary)), processes=1)
        coherence = estimator.compare_models(models)
        rows = []
        for model, (_, score) in zip(models, coherence):
            bound = float(model.log_perplexity(corpus))
            rows.append({"K": model.num_topics, "coherence_cv": float(score), "log_perplexity_bound": bound, "perplexity_base2": float(2 ** -bound)})
        metrics = pd.DataFrame(rows)
        metrics.to_csv(metrics_path, index=False)
    if not np.isfinite(metrics["coherence_cv"]).all():
        raise ValueError("Coherencia no finita; no seleccionar K sin revisar")
    best_k = int(metrics.loc[metrics["coherence_cv"].idxmax(), "K"])
    model = models[args.topics.index(best_k)]
    model.save(str(models_dir / "duque_lda_final.model"))
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    axes[0].plot(metrics["K"], metrics["coherence_cv"], "o-", color="#237c69")
    axes[0].axvline(best_k, color="#b8474b", linestyle="--")
    axes[0].set(title="Coherencia c_v de entrenamiento", xlabel="K", ylabel="c_v")
    axes[1].plot(metrics["K"], metrics["perplexity_base2"], "o-", color="#b8474b")
    axes[1].set(title="Perplejidad aproximada de entrenamiento", xlabel="K", ylabel="2 elevado a -bound")
    save_figure(output, "lda_optimization.png")
    topic_rows = []
    for topic in range(best_k):
        for word, weight in model.show_topic(topic, topn=10):
            topic_rows.append({"topic": topic, "palabra": word, "peso": float(weight)})
    pd.DataFrame(topic_rows).to_csv(output / "lda_topics.csv", index=False)
    probabilities = np.empty((len(corpus), best_k), dtype=np.float32)
    for position, bow in enumerate(corpus):
        probabilities[position] = [probability for _, probability in model.get_document_topics(bow, minimum_probability=0.0, per_word_topics=False)]
        if position and position % 100000 == 0:
            logging.info("Inferencia %s/%s", position, len(corpus))
    assert np.allclose(probabilities.sum(axis=1), 1, atol=1e-5)
    assignments = frame[["article_id", "source_id", "published_date", "year", "date_precision", "title_source"]].copy()
    assignments["dominant_topic"] = -1
    assignments["topic_confidence"] = 0.0
    assignments.loc[indices, "dominant_topic"] = probabilities.argmax(axis=1)
    assignments.loc[indices, "topic_confidence"] = probabilities.max(axis=1)
    assignments.to_parquet(output / "document_topics.parquet", index=False)
    counts = assignments.groupby(["source_id", "dominant_topic"]).size().unstack(fill_value=0)
    counts.to_csv(output / "topics_by_medium.csv")
    counts.plot.bar(stacked=True, figsize=(11, 5), colormap="tab20")
    plt.ylabel("Articulos; -1 = sin vocabulario LDA")
    plt.title("Topico dominante por medio (conteos)")
    plt.legend(title="Topico", bbox_to_anchor=(1.02, 1))
    save_figure(output, "topics_by_medium.png")
    proportions = counts.div(counts.sum(axis=1), axis=0)
    proportions.to_csv(output / "topics_by_medium_norm.csv")
    plt.figure(figsize=(11, 5))
    sns.heatmap(proportions, annot=True, fmt=".1%", cmap="YlGnBu")
    plt.title("Topicos por medio: proporciones, no medida de sesgo")
    save_figure(output, "topics_heatmap.png")
    logging.info("Preparando pyLDAvis con todo el corpus util")
    import pyLDAvis

    lengths = []
    term_frequency = np.zeros(len(dictionary), dtype=np.int64)
    for bow in corpus:
        lengths.append(sum(count for _, count in bow))
        for term_id, count in bow:
            term_frequency[term_id] += int(count)
    visualization = pyLDAvis.prepare(
        topic_term_dists=model.get_topics(), doc_topic_dists=probabilities,
        doc_lengths=lengths, vocab=[dictionary[term_id] for term_id in range(len(dictionary))],
        term_frequency=term_frequency, mds="mmds", sort_topics=False, n_jobs=1,
    )
    pyLDAvis.save_html(visualization, str(output / "lda_visualization.html"))
    return {"best_k": best_k, "coherence_cv": float(metrics["coherence_cv"].max()), "vocabulario_lda": len(dictionary), "documentos_lda": len(corpus), "sin_vocabulario_lda": len(frame) - len(corpus), "topics_grid": args.topics, "passes": args.passes, "iterations": 50, "seed": 42}


def run(args):
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / "figuras").mkdir(exist_ok=True)
    config = {"input_sha256": sha256(args.input), "topics": args.topics, "passes": args.passes, "no_below": args.no_below, "core_sha256": sha256(Path(__file__).with_name("core.py"))}
    config_path = output / "config.json"
    if config_path.exists() and json.loads(config_path.read_text()) != config:
        raise ValueError("El checkpoint pertenece a otro corpus/configuracion; usar otra carpeta de salida")
    save_json(config_path, config)
    if args.stage == "deliverables":
        from deliverables import generate
        generate(output, args.report_dir.resolve())
        return
    logging.info("Cargando y tokenizando corpus completo")
    frame, stop_words = load_data(args.input)
    save_json(output / "stopwords.json", stop_words)
    metadata = corpus_profile(frame, output)
    metadata["textometry"] = textometry(frame, output)
    metadata["temas"] = event_analysis(frame, output)
    save_json(output / "resumen.json", metadata)
    logging.info("Textometria y eventos guardados: %s", output)
    if args.stage == "textometry":
        return
    metadata["lda"] = train_lda(frame, output, args)
    metadata["versions"] = {package: importlib.metadata.version(package) for package in ["gensim", "scipy", "numpy", "pandas", "scikit-learn", "pyLDAvis", "nltk"]}
    save_json(output / "resumen.json", metadata)
    from deliverables import generate
    generate(output, args.report_dir.resolve())
    logging.info("ENTREGA COMPLETA: K=%s; corpus=%s; resultados=%s", metadata["lda"]["best_k"], len(frame), output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("resultados"))
    parser.add_argument("--report-dir", type=Path, default=Path("../informe"))
    parser.add_argument("--topics", type=int, nargs="+", default=[3, 5, 7, 10, 15])
    parser.add_argument("--passes", type=int, default=10)
    parser.add_argument("--no-below", type=int, default=10)
    parser.add_argument("--stage", choices=["all", "textometry", "deliverables"], default="all")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("gensim").setLevel(logging.WARNING)
    run(parser.parse_args())