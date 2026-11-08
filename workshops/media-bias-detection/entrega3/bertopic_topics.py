"""BERTopic sobre los titulares, con las mismas salidas que el LDA.

Embeddings multilingües (paraphrase-multilingual-MiniLM-L12-v2) del titular
reconstruido → UMAP a 5 dimensiones → k-means (k tópicos) → c-TF-IDF sobre los
mismos tokens del LDA (stopwords de dominio y bigramas de Phrases), para que el
vocabulario de los tópicos sea comparable entre modelos.

k-means en vez de HDBSCAN: HDBSCAN deja como ruido una parte grande de los
titulares (suele ser 30–40 %) y las participaciones por medio dejarían de ser
comparables con las del LDA. Con k-means cada titular tiene un tópico; θ es
una asignación dura (one-hot).

Se ajusta sobre la muestra balanceada de `prepare` y se aplica a todo el
corpus. La estabilidad se mide igual que en el LDA: se repite con otras
semillas (UMAP y k-means) y se emparejan los tópicos.

Los titulares de ejemplo (topic_examples.csv) son los más cercanos al
centroide de embeddings de cada tópico; la columna es `similitud_centroide`
(coseno), no `theta`, porque con θ one-hot todos empatan en 1.

Después: python topics.py --model bertopic --stage compare --output <misma carpeta>
"""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

import numpy as np
import pandas as pd
from gensim.corpora import Dictionary
from gensim.models import CoherenceModel

import topics as T

EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def embed(titles: list[str], cache: Path, batch: int) -> np.ndarray:
    if cache.exists():
        return np.load(cache)
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(EMBEDDING_MODEL, device="cpu")
    t0 = time.monotonic()
    emb = model.encode(titles, batch_size=batch, show_progress_bar=False, normalize_embeddings=True,
                       convert_to_numpy=True).astype(np.float32)
    logging.info("Embeddings de %s titulares en %.0f s", len(titles), time.monotonic() - t0)
    np.save(cache, emb)
    return emb


def fit(docs, emb, sample, k, seed):
    from bertopic import BERTopic
    from sklearn.cluster import KMeans
    from sklearn.feature_extraction.text import CountVectorizer
    from umap import UMAP

    model = BERTopic(
        umap_model=UMAP(n_neighbors=15, n_components=5, min_dist=0.0, metric="cosine", random_state=seed),
        hdbscan_model=KMeans(n_clusters=k, random_state=seed, n_init=10),
        # Los docs ya vienen tokenizados y unidos por espacios: un token = una palabra o bigrama.
        vectorizer_model=CountVectorizer(token_pattern=r"\S+", min_df=20, lowercase=False),
        calculate_probabilities=False, verbose=False,
    )
    t0 = time.monotonic()
    model.fit([docs[i] for i in sample], emb[sample])
    logging.info("BERTopic semilla %s ajustado en %.0f s", seed, time.monotonic() - t0)
    t0 = time.monotonic()
    assigned, _ = model.transform(docs, emb)
    logging.info("Asignación de %s titulares en %.0f s", len(docs), time.monotonic() - t0)
    ctfidf = model.c_tf_idf_.toarray()
    ids = sorted(t for t in set(model.topics_) if t >= 0)
    topic_word = ctfidf[[model._outliers + t for t in ids]]
    topic_word = topic_word / topic_word.sum(axis=1, keepdims=True)
    vocab = list(model.vectorizer_model.get_feature_names_out())
    remap = {t: i for i, t in enumerate(ids)}
    return np.array([remap.get(t, -1) for t in assigned]), topic_word, vocab


def class_tfidf(docs: list[str], assigned: np.ndarray, vocab: list[str]) -> np.ndarray:
    """c-TF-IDF de BERTopic (tf por clase normalizado × log(1 + A / f_t)) con un
    vocabulario fijo: el del diccionario del LDA.

    No se usa el c_tf_idf_ interno: BERTopic ajusta su CountVectorizer sobre un
    "documento" por tópico, así que `min_df` cuenta tópicos y no titulares (con
    min_df=20 sólo sobrevivían 164 palabras). Con un vocabulario fijo, además,
    las semillas son comparables palabra a palabra.
    """
    from sklearn.feature_extraction.text import CountVectorizer

    counts = CountVectorizer(token_pattern=r"\S+", lowercase=False, vocabulary=vocab).transform(docs)
    k = int(assigned.max()) + 1
    ok = assigned >= 0
    import scipy.sparse as sp

    member = sp.csr_matrix((np.ones(ok.sum()), (assigned[ok], np.flatnonzero(ok))), shape=(k, len(docs)))
    tf = np.asarray((member @ counts).todense(), dtype=float)
    avg_words = tf.sum() / k
    idf = np.log(1 + avg_words / np.maximum(tf.sum(axis=0), 1))
    w = (tf / np.maximum(tf.sum(axis=1, keepdims=True), 1)) * idf
    return w / w.sum(axis=1, keepdims=True)


def centroid_examples(frame: pd.DataFrame, assigned: np.ndarray, emb: np.ndarray, min_tokens: int = 4,
                      per_source: int = 4, n: int = 20) -> pd.DataFrame:
    """Titulares de ejemplo de cada tópico, los más cercanos a su centroide.

    Con θ one-hot todos los titulares de un tópico empatan, así que el criterio
    del LDA (mayor θ) elegía casi al azar. Aquí el centroide es la media de los
    embeddings (normalizados) de los titulares asignados al tópico, y el puntaje
    `similitud_centroide` es el coseno de cada titular con ese centroide. Se
    mantiene el reparto del LDA: titulares con ≥ `min_tokens` tokens, hasta
    `per_source` por medio y `n` en total.
    """
    ntok = frame["tokens"].map(len).to_numpy()
    rows = []
    for k in range(int(assigned.max()) + 1):
        members = np.flatnonzero(assigned == k)
        if not len(members):
            continue
        centroid = emb[members].mean(axis=0)
        centroid = centroid / np.linalg.norm(centroid)
        cand = members[ntok[members] >= min_tokens]
        sims = emb[cand] @ centroid
        pick = (frame.iloc[cand][["source_id", "government_id", "title"]]
                .assign(similitud_centroide=sims).sort_values("similitud_centroide", ascending=False)
                .groupby("source_id", group_keys=False).head(per_source)
                .sort_values("similitud_centroide", ascending=False).head(n))
        rows.extend({"topic": k, "source_id": r.source_id, "government_id": r.government_id,
                     "similitud_centroide": round(float(r.similitud_centroide), 4), "title": r.title}
                    for r in pick.itertuples())
    return pd.DataFrame(rows)


def one_hot(assigned: np.ndarray, k: int) -> np.ndarray:
    theta = np.zeros((len(assigned), k), dtype=np.float32)
    ok = assigned >= 0
    theta[np.flatnonzero(ok), assigned[ok]] = 1.0
    theta[~ok] = np.nan
    return theta


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, required=True, help="Carpeta con prepared.parquet (de topics.py)")
    parser.add_argument("--k", type=int, default=20)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--stability-seeds", type=int, nargs="+", default=[7, 123])
    parser.add_argument("--batch", type=int, default=256)
    parser.add_argument("--cv-docs", type=int, default=100_000)
    parser.add_argument("--only-examples", action="store_true",
                        help="Sólo regenerar asignaciones, términos y ejemplos desde las cachés")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    out = args.output.resolve()
    res = out / "bertopic"
    (res / "figuras").mkdir(parents=True, exist_ok=True)
    frame = T._load_prepared(out)
    docs = [" ".join(t) for t in frame["tokens"]]
    emb = embed(frame["title"].tolist(), res / "embeddings.npy", args.batch)
    sample = np.flatnonzero(frame["in_sample"].to_numpy())

    fits = {}
    for seed in [args.seed, *args.stability_seeds]:
        cache = res / f"asignacion_seed{seed}.npz"
        if cache.exists():
            data = np.load(cache, allow_pickle=True)
            fits[seed] = (data["assigned"], data["topic_word"], list(data["vocab"]))
        else:
            fits[seed] = fit(docs, emb, sample, args.k, seed)
            np.savez(cache, assigned=fits[seed][0], topic_word=fits[seed][1], vocab=np.array(fits[seed][2]))

    dictionary = Dictionary.load(str(out / "modelos" / "dictionary.dict"))
    vocab = [dictionary[i] for i in range(len(dictionary))]
    fits = {seed: (a, class_tfidf(docs, a, vocab), vocab) for seed, (a, _, _) in fits.items()}
    assigned, topic_word, vocab = fits[args.seed]
    theta = one_hot(assigned, topic_word.shape[0])
    np.save(res / "theta.npy", theta)
    empty = assigned < 0
    T.save_assignments(frame, theta, empty, res)
    T.save_examples(frame, theta, topic_word, vocab, res)
    # Sustituye los ejemplos por θ (empatados en one-hot) por los más cercanos al centroide.
    centroid_examples(frame, assigned, emb).to_csv(res / "topic_examples.csv", index=False)
    if args.only_examples:
        return

    rows, matrices, jaccards = [], {}, {}
    for seed in args.stability_seeds:
        rows += T.stability_rows(topic_word, fits[seed][1], vocab, seed, matrices, jaccards)
    T.save_stability(rows, matrices, jaccards, args.stability_seeds, res)

    keep = ~empty
    meta = frame.loc[keep, ["government_id", "month", "source_id"]]
    thetas = {"base": theta[keep]}
    for seed in args.stability_seeds:
        thetas[f"semilla_{seed}"] = np.nan_to_num(one_hot(fits[seed][0], fits[seed][1].shape[0]))[keep]
    T.save_robustness(thetas, meta, pd.read_csv(res / "topic_stability.csv"), args.stability_seeds, res)

    # Coherencia c_v con el mismo diccionario y textos que el LDA, para comparar modelos.
    words = [T.top_words(topic_word, vocab, k, 10)
             for k in range(topic_word.shape[0])]
    texts = [t.tolist() for t in frame.loc[frame["in_sample"], "tokens"]]
    rng = np.random.default_rng(args.seed)
    texts = [texts[i] for i in rng.choice(len(texts), size=min(args.cv_docs, len(texts)), replace=False)]
    cv = CoherenceModel(topics=words, texts=texts, dictionary=dictionary, coherence="c_v", processes=8).get_coherence()
    T.save_json(res / "bertopic.json", {
        "k": int(topic_word.shape[0]), "coherence_cv": float(cv), "embedding_model": EMBEDDING_MODEL,
        "clustering": f"UMAP(5d, coseno) + k-means (k={args.k})", "documentos": len(frame),
        "ctfidf": "propio, vocabulario del diccionario LDA",
        "muestra_ajuste": int(len(sample)),
    })


if __name__ == "__main__":
    main()
