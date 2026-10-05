import argparse
import json
import logging
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlsplit

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from gensim.models import LdaModel
from news_corpus.pipeline.enrich import derive_from_url
from scipy.cluster.hierarchy import dendrogram, linkage
from scipy.spatial.distance import jensenshannon, squareform
from scipy.stats import fisher_exact, linregress, pearsonr, spearmanr

from analysis import TOPICS, load_data, sha256
from core import counter_metrics, keyword_pattern, msttr
from research_stats import block_bootstrap_mean, chi_square_counts, holm_adjust, wilson_interval


MAIN_MEDIA = ["blu_radio", "el_tiempo", "la_republica", "noticias_caracol", "noticias_rcn"]


def clean_json(value):
    if isinstance(value, dict):
        return {str(key): clean_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean_json(item) for item in value]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


class Research:
    def __init__(self, args):
        self.args = args
        self.output = args.output.resolve()
        self.output.mkdir(parents=True, exist_ok=True)
        (self.output / "figuras").mkdir(exist_ok=True)
        self.results = args.results.resolve()
        self.summary = json.loads((self.results / "resumen.json").read_text())
        self.frame, self.stop_words = load_data(args.input)
        self.rows = []
        self.checks = []
        self.evidence = {}
        if args.db_evidence and args.db_evidence.exists():
            self.evidence = json.loads(args.db_evidence.read_text())

    def record(self, section, metric, value, medium="all", theme="", topic="", unit="", count=None, low=None, high=None, method="descriptivo", status="calculado", source=""):
        self.rows.append({"section": section, "metric": metric, "source_id": medium, "tema": theme, "topic_id": topic, "value": value, "unit": unit, "n": count, "low": low, "high": high, "method": method, "status": status, "source_file": source})

    def check(self, name, passed, detail):
        self.checks.append({"check": name, "passed": bool(passed), "detail": detail})
        if not passed:
            raise AssertionError(f"{name}: {detail}")

    def save_table(self, name, table):
        table.to_csv(self.output / name, index=False)

    def figure(self, name):
        plt.tight_layout()
        plt.savefig(self.output / "figuras" / name, dpi=150, bbox_inches="tight")
        plt.close()

    def phase1(self):
        frame = self.frame
        self.check("input_rows", len(frame) == self.summary["articulos"], str(len(frame)))
        self.check("input_checksum", sha256(self.args.input) == json.loads((self.results / "config.json").read_text())["input_sha256"], "SHA-256 coincide")
        self.check("unique_ids", frame["article_id"].is_unique, "article_id unico")
        self.check("date_range", frame["published_date"].between("2018-08-07", "2022-08-06").all(), "Intervalo semiabierto Duque")
        self.check("six_sources", frame["source_id"].nunique() == 6, "Cinco medios principales y Cambio")
        self.check("titles", frame["title"].notna().sum() == self.summary["con_titulo"], str(frame["title"].notna().sum()))
        coverage = frame.groupby("source_id").agg(articles=("article_id", "size"), titles=("title", "count"), first_date=("published_date", "min"), last_date=("published_date", "max"))
        self.save_table("input_coverage.csv", coverage.reset_index())
        normalized_duplicates = int(frame.loc[frame["title_norm"].ne(""), "title_norm"].duplicated(keep=False).sum())
        self.record("integrity", "articles", len(frame), unit="documents", source="input Parquet")
        self.record("integrity", "missing_title", int(frame["title"].isna().sum()), unit="documents", source="input Parquet")
        self.record("integrity", "title_coverage_pct", 100 * frame["title"].notna().mean(), unit="percent", source="input Parquet")
        self.record("integrity", "duplicated_normalized_title_rows", normalized_duplicates, unit="documents", source="input Parquet")
        for medium, group in frame.groupby("source_id"):
            for source, count in group["title_source"].fillna("missing").value_counts().items():
                self.record("integrity", f"title_source_{source}", int(count), medium, unit="documents", source="input Parquet")
        missing = frame.loc[frame["title"].isna(), ["article_id", "source_id", "url"]].copy()
        missing["derived_retry"] = missing["url"].map(lambda url: derive_from_url(url).title)
        missing["slug_raw"] = missing["url"].map(lambda url: unquote(urlsplit(url).path.rsplit("/", 1)[-1]))
        self.check("missing_not_derivable", missing["derived_retry"].isna().all(), "Todos siguen rechazados por el parser de Kelly")
        self.save_table("missing_title_urls.csv", missing)
        cambio = frame.loc[frame["source_id"].eq("cambio"), ["article_id", "title", "url", "published_date", "title_source", "date_precision"]]
        self.save_table("cambio_titles.csv", cambio)
        before = self.evidence.get("duque_before", {})
        if before:
            self.check("before_after_same_rows", before["articles"] == len(frame), "Original y export tienen mismo corte y numero de filas")
            self.record("integrity", "titles_before_enrich", before["titles"], unit="documents", source="db_evidence.json")
            self.record("integrity", "titles_gained", int(frame["title"].notna().sum()) - before["titles"], unit="documents", source="DB original + Parquet")
        global_cambio = self.evidence.get("cambio_global", {})
        self.audit = {
            "cambio_articles": len(cambio), "cambio_start": cambio["published_date"].min().date().isoformat(),
            "cambio_end": cambio["published_date"].max().date().isoformat(), "cambio_global": global_cambio,
            "normalized_duplicate_rows": normalized_duplicates, "before": before,
            "month_precision": int(frame["date_precision"].eq("month").sum()),
            "non_duque_assignment": int(frame["government_id"].ne("duque").sum()),
        }

    def phase2(self):
        random = np.random.default_rng(42)
        global_counter = Counter()
        zipf_rows = []
        equal_rows = []
        specific_ngrams = []
        monthly = []
        for medium, subset in self.frame.groupby("source_id", sort=True):
            counter = Counter()
            bigrams = Counter()
            trigrams = Counter()
            all_tokens = []
            for tokens in subset["tokens"]:
                counter.update(tokens)
                all_tokens.extend(tokens)
                bigrams.update(" ".join(tokens[start:start + 2]) for start in range(len(tokens) - 1))
                trigrams.update(" ".join(tokens[start:start + 3]) for start in range(len(tokens) - 2))
            global_counter.update(counter)
            frequencies = np.array(sorted(counter.values(), reverse=True))
            ranks = np.arange(1, len(frequencies) + 1)
            mask = (ranks >= 10) & (ranks <= 10000) & (frequencies > 1)
            regression = linregress(np.log(ranks[mask]), np.log(frequencies[mask]))
            correlation = pearsonr(np.log(ranks), np.log(frequencies))
            zipf_rows.append({"source_id": medium, **counter_metrics(counter), "pearson_r": float(correlation.statistic), "slope": float(regression.slope), "r2": float(regression.rvalue ** 2), "fit_ranks": int(mask.sum()), "hapax": int((frequencies == 1).sum())})
            self.record("zipf", "pearson_r", float(correlation.statistic), medium, method="rank-frequency descriptive", source="input tokens")
            self.record("zipf", "slope", float(regression.slope), medium, method="ranks 10-10000; not power-law test", source="input tokens")
            for size, counts in [(2, bigrams), (3, trigrams)]:
                for phrase, count in counts.most_common(10):
                    specific_ngrams.append({"source_id": medium, "size": size, "ngram": phrase, "count": count, "count_per_1000_titles": 1000 * count / subset["title"].notna().sum()})
            if len(all_tokens) >= self.args.token_budget:
                encoded = np.asarray(pd.factorize(np.asarray(all_tokens, dtype=object))[0], dtype=np.int32)
                values = [len(np.unique(encoded[random.choice(len(encoded), size=self.args.token_budget, replace=False)])) / self.args.token_budget for _ in range(self.args.repetitions)]
                low, high = np.quantile(values, [0.025, 0.975])
                equal_rows.append({"source_id": medium, "budget": self.args.token_budget, "repetitions": self.args.repetitions, "ttr_mean": float(np.mean(values)), "q025": float(low), "q975": float(high), "status": "equal-token rarefaction, not publisher CI"})
                self.record("diversity", "equal_token_ttr", float(np.mean(values)), medium, count=self.args.token_budget, low=float(low), high=float(high), method="100 subsamples without replacement; not inferential CI", source="input tokens")
            else:
                equal_rows.append({"source_id": medium, "budget": self.args.token_budget, "repetitions": 0, "ttr_mean": np.nan, "q025": np.nan, "q975": np.nan, "status": "insufficient tokens; excluded"})
            for month, month_frame in subset.groupby(subset["published_date"].dt.to_period("M")):
                tokens = [token for document in month_frame["tokens"] for token in document]
                if len(tokens) >= 50:
                    monthly.append({"source_id": medium, "month": str(month), "msttr50": msttr(tokens), "tokens": len(tokens)})
        self.save_table("zipf_by_medium.csv", pd.DataFrame(zipf_rows))
        self.save_table("diversity_equal_tokens.csv", pd.DataFrame(equal_rows))
        self.save_table("ngrams_by_medium.csv", pd.DataFrame(specific_ngrams))
        monthly = pd.DataFrame(monthly)
        self.save_table("diversity_monthly.csv", monthly)
        common_months = monthly.pivot(index="month", columns="source_id", values="msttr50")[MAIN_MEDIA].dropna()
        month_means = common_months.mean()
        highest, lowest = month_means.idxmax(), month_means.idxmin()
        interval = block_bootstrap_mean((common_months[highest] - common_months[lowest]).to_numpy())
        self.record("diversity", "paired_month_msttr_difference", interval["mean"], f"{highest} vs {lowest}", count=interval["months"], low=interval["low"], high=interval["high"], method="circular month blocks length3; 1000 resamples; exploratory", source="diversity_monthly.csv")
        self.save_table("diversity_month_difference.csv", pd.DataFrame([{"highest": highest, "lowest": lowest, **interval}]))
        frequencies = pd.DataFrame(global_counter.most_common(), columns=["palabra", "frecuencia"])
        stored = pd.read_csv(self.results / "frecuencias.csv", keep_default_na=False)
        self.check("global_frequencies", dict(frequencies.values) == dict(stored[["palabra", "frecuencia"]].values), "Reconteo exacto de tokens")
        self.check("global_vocabulary", len(global_counter) == self.summary["textometry"]["vocabulario"], "Vocabulario coincide")
        frequencies["rank"] = np.arange(1, len(frequencies) + 1)
        mask = frequencies["rank"].between(10, 10000) & frequencies["frecuencia"].gt(1)
        regression = linregress(np.log(frequencies.loc[mask, "rank"]), np.log(frequencies.loc[mask, "frecuencia"]))
        frequencies["residual_log"] = np.log(frequencies["frecuencia"]) - (regression.intercept + regression.slope * np.log(frequencies["rank"]))
        self.save_table("zipf_residuals.csv", frequencies.loc[mask].assign(abs_residual=lambda data: data["residual_log"].abs()).sort_values("abs_residual", ascending=False).head(20))
        diversity = pd.read_csv(self.results / "diversidad_por_medio.csv")
        diversity.plot.bar(x="source_id", y="ttr_agregado", legend=False, figsize=(9, 4), color="#b8474b")
        plt.title("TTR agregado: tamano desigual, no ranking editorial")
        self.figure("ttr_por_medio.png")
        comparable = pd.DataFrame(equal_rows).dropna(subset=["ttr_mean"])
        plt.figure(figsize=(9, 4))
        plt.errorbar(comparable["source_id"], comparable["ttr_mean"], yerr=[comparable["ttr_mean"] - comparable["q025"], comparable["q975"] - comparable["ttr_mean"]], fmt="o", color="#237c69")
        plt.xticks(rotation=30)
        plt.ylabel(f"TTR con {self.args.token_budget} tokens")
        plt.title("Rarefaccion descriptiva: 100 submuestras, Cambio excluido")
        self.figure("diversity_equal_tokens.png")
        plt.figure(figsize=(9, 4))
        for medium, group in pd.DataFrame(zipf_rows).groupby("source_id"):
            row = group.iloc[0]
            plt.scatter(row["slope"], row["r2"], label=medium)
        plt.xlabel("Pendiente descriptiva")
        plt.ylabel("R2 del ajuste")
        plt.title("Ajuste por medio: no prueba de potencia pura")
        plt.legend()
        self.figure("zipf_by_medium.png")

    def phase3(self):
        denominators = self.frame.loc[self.frame["title"].notna()].groupby("source_id").size()
        stored = pd.read_csv(self.results / "eventos_polemicos.csv").set_index(["tema", "source_id"])
        tests = []
        rates = []
        sensitivity = []
        monthly_rows = []
        for theme, keywords in TOPICS.items():
            matched = self.frame["title_norm"].str.contains(keyword_pattern(keywords))
            counts = self.frame.loc[matched].groupby("source_id").size().reindex(denominators.index, fill_value=0)
            for medium, total in denominators.items():
                count = int(counts[medium])
                self.check(f"event_{theme}_{medium}", count == int(stored.loc[(theme, medium), "articulos"]), "Keywords recontadas desde input")
                low, high = wilson_interval(count, int(total))
                rates.append({"tema": theme, "source_id": medium, "count": count, "total_titles": int(total), "pct": 100 * count / total, "wilson_low_pct": 100 * low, "wilson_high_pct": 100 * high})
                self.record("events", "keyword_rate_pct", 100 * count / total, medium, theme, unit="percent", count=int(total), low=100 * low, high=100 * high, method="title denominator; Wilson conditional binomial", source="input + keyword rules")
            table = np.column_stack([counts.loc[MAIN_MEDIA].to_numpy(), (denominators.loc[MAIN_MEDIA] - counts.loc[MAIN_MEDIA]).to_numpy()])
            test = {"tema": theme, **chi_square_counts(table)}
            tests.append(test)
            cambio_count, cambio_total = int(counts["cambio"]), int(denominators["cambio"])
            other_count, other_total = int(counts.loc[MAIN_MEDIA].sum()), int(denominators.loc[MAIN_MEDIA].sum())
            fisher = fisher_exact([[cambio_count, cambio_total - cambio_count], [other_count, other_total - other_count]])
            self.record("events", "cambio_fisher_p", float(fisher.pvalue), "cambio", theme, count=cambio_total, method="exploratory exact 2x2; not representative sampling", source="input counts")
            subset = self.frame.loc[self.frame["date_precision"].eq("day") & self.frame["title"].notna()]
            day_denominator = subset.groupby("source_id").size()
            day_count = subset.loc[matched.loc[subset.index]].groupby("source_id").size()
            for medium, total in day_denominator.items():
                count = int(day_count.get(medium, 0))
                sensitivity.append({"tema": theme, "source_id": medium, "day_titles": int(total), "day_matches": count, "pct_day": 100 * count / total})
            month_frame = self.frame.loc[self.frame["title"].notna(), ["source_id", "published_date"]].copy()
            month_frame["month"] = month_frame["published_date"].dt.to_period("M").astype(str)
            month_frame["matched"] = matched.loc[month_frame.index]
            group = month_frame.groupby(["source_id", "month"])["matched"].agg(["sum", "size"])
            group["pct"] = 100 * group["sum"] / group["size"]
            for (medium, month), row in group.iterrows():
                monthly_rows.append({"tema": theme, "source_id": medium, "month": month, "matches": int(row["sum"]), "titles": int(row["size"]), "pct": row["pct"]})
            main_rates = counts.loc[MAIN_MEDIA] / denominators.loc[MAIN_MEDIA]
            maximum, minimum = main_rates.idxmax(), main_rates.idxmin()
            paired = group["pct"].unstack("source_id")[[maximum, minimum]].dropna()
            interval = block_bootstrap_mean((paired[maximum] - paired[minimum]).to_numpy())
            self.record("events", "paired_month_difference_pp", interval["mean"], f"{maximum} vs {minimum}", theme, unit="percentage_points", count=interval["months"], low=interval["low"], high=interval["high"], method="circular month blocks length3; 1000 resamples; exploratory", source="input monthly rates")
        adjusted = holm_adjust([test["p"] for test in tests])
        for test, probability in zip(tests, adjusted):
            test["p_holm"] = float(probability)
            self.record("events", "chi_square_p_holm", float(probability), theme=test["tema"], count=test["n"], method="5 media x yes/no; Holm3; archival dependence caveat", source="event_tests.csv")
            self.record("events", "cramers_v", test["cramers_v"], theme=test["tema"], count=test["n"], source="event_tests.csv")
        self.save_table("event_rates.csv", pd.DataFrame(rates))
        self.save_table("event_tests.csv", pd.DataFrame(tests))
        self.save_table("event_sensitivity_day.csv", pd.DataFrame(sensitivity))
        self.save_table("event_month_rates.csv", pd.DataFrame(monthly_rows))
        pivot = pd.DataFrame(rates).pivot(index="source_id", columns="tema", values="pct")
        pivot.loc[MAIN_MEDIA].T.plot.bar(figsize=(11, 5))
        plt.ylabel("% de titulos del medio")
        plt.title("Keywords: denominadores por medio, no composicion de matches")
        self.figure("event_rates.png")
        correlations = pivot.loc[MAIN_MEDIA].T.corr()
        correlations.to_csv(self.output / "event_profile_correlations.csv")
        self.event_tests = tests

    def phase4(self):
        scores = pd.read_csv(self.results / "lda_optimization.csv")
        best = int(scores.loc[scores["coherence_cv"].idxmax(), "K"])
        self.check("best_k", best == self.summary["lda"]["best_k"], "Argmax coincide")
        sorted_scores = scores.sort_values("coherence_cv", ascending=False)
        gap = float(sorted_scores.iloc[0]["coherence_cv"] - sorted_scores.iloc[1]["coherence_cv"])
        model = LdaModel.load(str(self.results / "modelos" / f"lda_k{best}.model"))
        stored_terms = pd.read_csv(self.results / "lda_topics.csv")
        overlap = []
        terms = []
        for topic in range(best):
            words = model.show_topic(topic, topn=10)
            expected = stored_terms.loc[stored_terms["topic"].eq(topic)]
            self.check(f"topic_terms_{topic}", [word for word, _ in words] == expected["palabra"].tolist(), "Terminos del modelo iguales al CSV")
            self.check(f"topic_weights_{topic}", np.allclose([weight for _, weight in words], expected["peso"]), "Pesos del modelo iguales al CSV")
            terms.extend({"topic": topic, "word": word, "weight": float(weight)} for word, weight in words)
        for first in range(best):
            for second in range(first + 1, best):
                words_first = {word for word, _ in model.show_topic(first, topn=10)}
                words_second = {word for word, _ in model.show_topic(second, topn=10)}
                overlap.append({"first": first, "second": second, "jaccard_top10": len(words_first & words_second) / len(words_first | words_second), "probability_overlap": float(np.minimum(model.get_topics()[first], model.get_topics()[second]).sum()), "shared_top10": ", ".join(sorted(words_first & words_second))})
        self.save_table("topic_terms_verified.csv", pd.DataFrame(terms))
        self.save_table("topic_overlap.csv", pd.DataFrame(overlap))
        assignments = pd.read_parquet(self.results / "document_topics.parquet")
        self.check("assignment_ids", assignments["article_id"].is_unique and set(assignments["article_id"]) == set(self.frame["article_id"]), "Todos los IDs coinciden")
        merged = self.frame.merge(assignments[["article_id", "source_id", "published_date", "dominant_topic", "topic_confidence"]], on="article_id", suffixes=("", "_assignment"), validate="one_to_one")
        self.check("assignment_source", merged["source_id"].equals(merged["source_id_assignment"]), "Medios alineados por ID")
        self.check("assignment_date", merged["published_date"].equals(pd.to_datetime(merged["published_date_assignment"])), "Fechas alineadas por ID")
        vocabulary = model.id2word.token2id
        merged["known_tokens"] = merged["tokens"].map(lambda tokens: sum(word in vocabulary for word in tokens))
        merged["vocab_coverage"] = merged["known_tokens"] / merged["num_tokens"].replace(0, np.nan)
        self.check("excluded_empty_bow", merged["dominant_topic"].eq(-1).equals(merged["known_tokens"].eq(0)), "Topico -1 exactamente sin vocabulario util")
        assigned = merged.loc[merged["dominant_topic"].ge(0)]
        self.check("confidence_range", assigned["topic_confidence"].between(0, 1).all(), "Probabilidades validas")
        low_confidence = int(assigned["topic_confidence"].lt(0.3).sum())
        confidence_rows = []
        for medium, group in merged.groupby("source_id"):
            eligible = group.loc[group["dominant_topic"].ge(0)]
            confidence_rows.append({"source_id": medium, "all_documents": len(group), "assigned": len(eligible), "excluded": int(group["dominant_topic"].eq(-1).sum()), "assigned_confidence_lt03": int(eligible["topic_confidence"].lt(0.3).sum()), "assigned_confidence_mean": float(eligible["topic_confidence"].mean()), "vocab_coverage_mean": float(eligible["vocab_coverage"].mean())})
        self.save_table("topic_confidence.csv", pd.DataFrame(confidence_rows))
        correlation = spearmanr(assigned["topic_confidence"], assigned["vocab_coverage"])
        length_correlation = spearmanr(assigned["topic_confidence"], assigned["known_tokens"])
        self.save_table("low_confidence_examples.csv", assigned.loc[assigned["topic_confidence"].lt(0.3), ["article_id", "source_id", "title", "url", "num_tokens", "known_tokens", "vocab_coverage", "dominant_topic", "topic_confidence"]].sort_values("topic_confidence").head(40))
        counts = pd.crosstab(merged["source_id"], merged["dominant_topic"])
        stored_counts = pd.read_csv(self.results / "topics_by_medium.csv", index_col=0)
        stored_counts.columns = stored_counts.columns.astype(int)
        self.check("topic_counts", counts.equals(stored_counts), "Conteos recalculados por IDs")
        all_proportions = counts.div(counts.sum(axis=1), axis=0)
        stored_proportions = pd.read_csv(self.results / "topics_by_medium_norm.csv", index_col=0)
        stored_proportions.columns = stored_proportions.columns.astype(int)
        self.check("topic_proportions", np.allclose(all_proportions, stored_proportions), "Proporciones exactas, incluido -1")
        conditional = counts.drop(columns=-1).div(counts.drop(columns=-1).sum(axis=1), axis=0)
        conditional.to_csv(self.output / "topic_proportions_assigned.csv")
        distances = pd.DataFrame(0.0, index=conditional.index, columns=conditional.index)
        for first in conditional.index:
            for second in conditional.index:
                distances.loc[first, second] = jensenshannon(conditional.loc[first], conditional.loc[second], base=2)
                if first < second:
                    self.record("lda", "js_distance", distances.loc[first, second], f"{first} vs {second}", unit="distance [0,1]", method="JS distance base2, assigned documents", source="topic_distances.csv")
        distances.to_csv(self.output / "topic_distances.csv")
        main_table = counts.loc[MAIN_MEDIA].drop(columns=-1)
        centroid = main_table.sum(axis=0) / main_table.to_numpy().sum()
        for medium in conditional.index:
            self.record("lda", "js_distance_main_centroid", float(jensenshannon(conditional.loc[medium], centroid, base=2)), medium, count=int(counts.loc[medium].sum()), method="weighted five-media assigned-document centroid", source="topic_proportions_assigned.csv")
        topic_test = chi_square_counts(main_table.to_numpy())
        self.save_table("topic_independence.csv", pd.DataFrame([topic_test]))
        plt.figure(figsize=(9, 6))
        sns.heatmap(conditional, annot=True, fmt=".1%", cmap="YlGnBu")
        plt.title("Topicos entre documentos asignados: Cambio n pequeno")
        self.figure("topics_assigned_heatmap.png")
        plt.figure(figsize=(9, 5))
        sns.heatmap(distances, annot=True, fmt=".3f", cmap="YlGnBu")
        plt.title("Distancia Jensen-Shannon; Cambio descriptivo, no representativo")
        self.figure("topic_distances.png")
        plt.figure(figsize=(9, 4))
        dendrogram(linkage(squareform(distances.loc[MAIN_MEDIA, MAIN_MEDIA].to_numpy(), checks=True), method="average"), labels=MAIN_MEDIA)
        plt.title("Agrupacion descriptiva de cinco medios; no clustering validado")
        self.figure("media_dendrogram.png")
        fig, axes = plt.subplots(1, 2, figsize=(11, 4))
        axes[0].plot(scores["K"], scores["coherence_cv"], "o-")
        axes[0].set(title="Coherencia de entrenamiento", xlabel="K", ylabel="c_v")
        axes[1].plot(scores["K"], scores["perplexity_base2"], "o-")
        axes[1].set(title="Perplejidad de entrenamiento", xlabel="K", ylabel="Perplejidad", yscale="log")
        self.figure("lda_tradeoff.png")
        self.lda = {"best_k": best, "coherence_gap_next": gap, "runner_up_k": int(sorted_scores.iloc[1]["K"]), "no_assignment": int(merged["dominant_topic"].eq(-1).sum()), "assigned_low_confidence": low_confidence, "assigned_mean_confidence": float(assigned["topic_confidence"].mean()), "confidence_vocab_spearman": float(correlation.statistic), "confidence_length_spearman": float(length_correlation.statistic), "topic_test": topic_test, "seed_stability": "not measured: one seed per K"}
        self.record("lda", "coherence_gap_next", gap, topic=best, method="one seed; no uncertainty interval", source="lda_optimization.csv")
        self.record("lda", "excluded_no_bow", self.lda["no_assignment"], unit="documents", source="document_topics.parquet + dictionary")
        self.record("lda", "assigned_low_confidence", low_confidence, unit="documents", count=len(assigned), source="document_topics.parquet")
        self.record("lda", "confidence_vocab_spearman", self.lda["confidence_vocab_spearman"], count=len(assigned), method="descriptive association; no causal inference", source="input tokens + assignments")

    def run(self):
        for number in range(1, 5):
            logging.info("Research fase %s", number)
            getattr(self, f"phase{number}")()
        self.save_table("DATA_INSIGHTS_TABLES.csv", pd.DataFrame(self.rows))
        self.save_table("audit_checks.csv", pd.DataFrame(self.checks))
        metadata = clean_json({"audit": self.audit, "event_tests": self.event_tests, "lda": self.lda, "checks": len(self.checks), "all_checks_passed": all(check["passed"] for check in self.checks), "token_budget": self.args.token_budget, "repetitions": self.args.repetitions, "input_sha256": sha256(self.args.input)})
        (self.output / "research_metrics.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
        logging.info("Research calculado: %s verificaciones, %s metricas", len(self.checks), len(self.rows))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--results", type=Path, default=Path("resultados"))
    parser.add_argument("--output", type=Path, default=Path("research"))
    parser.add_argument("--db-evidence", type=Path, default=Path("research/db_evidence.json"))
    parser.add_argument("--token-budget", type=int, default=10000)
    parser.add_argument("--repetitions", type=int, default=100)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    Research(args).run()