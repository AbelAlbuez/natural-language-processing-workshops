"""Figuras del LDA Duque + Petro, con un único estilo.

Paleta: la de referencia del skill de visualización, validada con
`validate_palette.js` (5 medios: todas las pruebas pasan; aqua, amarillo y
magenta quedan bajo 3:1 de contraste, así que las series llevan etiqueta
directa). Los medios usan siempre el mismo color y los gobiernos otro par
(violeta y verde), para que nunca se confundan con un medio.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import FancyBboxPatch, Patch
from matplotlib.ticker import FuncFormatter, MaxNLocator, PercentFormatter

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"

MEDIA = ["el_tiempo", "blu_radio", "noticias_rcn", "noticias_caracol", "la_republica"]
MEDIA_NAMES = {
    "el_tiempo": "El Tiempo", "blu_radio": "Blu Radio", "noticias_rcn": "Noticias RCN",
    "noticias_caracol": "Noticias Caracol", "la_republica": "La República",
}
MEDIA_COLORS = {
    "el_tiempo": "#2a78d6", "blu_radio": "#eb6834", "noticias_rcn": "#1baf7a",
    "noticias_caracol": "#eda100", "la_republica": "#e87ba4",
}
SHORT = {"el_tiempo": "El Tiempo", "blu_radio": "Blu Radio", "noticias_rcn": "RCN",
         "noticias_caracol": "Caracol", "la_republica": "La República"}
GOV_NAMES = {"duque": "Duque", "petro": "Petro"}
GOV_COLORS = {"duque": "#6250d6", "petro": "#008300"}
BLUE = "#2a78d6"
RED = "#e34948"
NEUTRAL = "#f0efec"
SEQ_RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
SEQ = LinearSegmentedColormap.from_list("seq", [SURFACE, *SEQ_RAMP])
ORDINAL = ["#86b6ef", "#6da7ec", "#5598e7", "#3987e5", "#2a78d6", "#256abf", "#1c5cab"]
POSESION = pd.Timestamp("2022-08-07")
FUENTE = "Fuente: corpus news_corpus (dump 2026-10-04, slug procesado 2026-11-04)."

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10,
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "text.color": INK, "axes.labelcolor": INK2, "axes.titlecolor": INK,
    "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "axes.edgecolor": AXIS, "axes.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "xtick.color": MUTED, "ytick.color": MUTED, "xtick.labelcolor": INK2, "ytick.labelcolor": INK2,
    "legend.frameon": False, "legend.fontsize": 9, "lines.linewidth": 2,
})


SUFIJO = {"robusto": "", "parcial": " · parcial", "inestable": " · inestable"}


def etiqueta(labels: dict, robust: dict | None, k: int) -> str:
    """Etiqueta humana del tópico, marcada si no es robusto entre semillas."""
    return labels.get(k, f"T{k}") + (SUFIJO.get(robust.get(k), "") if robust else "")


def miles(n: float) -> str:
    return f"{n:,.0f}".replace(",", ".")


def _save(fig, out: Path, name: str, title: str, note: str, note_y: float = -0.01) -> None:
    fig.suptitle(title, x=0.01, y=1.03, ha="left", va="bottom", fontsize=13, fontweight="bold", color=INK)
    fig.text(0.01, note_y, textwrap.fill(note, 190), ha="left", va="top", fontsize=8, color=MUTED)
    fig.savefig(out / "figuras" / name, dpi=150, bbox_inches="tight")
    plt.close(fig)


def _possession(ax, label=True) -> None:
    ax.axvline(POSESION, color=INK2, lw=1, ls="--")
    if label:
        ax.text(POSESION, ax.get_ylim()[1], " posesión de Petro", va="top", ha="left", fontsize=8, color=INK2)


def _end_labels(ax, series: dict[str, pd.Series]) -> None:
    """Etiqueta directa al final de cada línea, separando las que chocan."""
    ends = sorted(((s.dropna().iloc[-1], m) for m, s in series.items()), reverse=True)
    lo, hi = ax.get_ylim()
    gap = (hi - lo) * 0.045
    placed = []
    for value, m in ends:
        y = value
        for p in placed:
            if abs(y - p) < gap:
                y = p - gap
        placed.append(y)
        ax.text(series[m].dropna().index[-1], y, "  " + MEDIA_NAMES[m], va="center", fontsize=8, color=INK2)


# ── datos ────────────────────────────────────────────────────────────────────


def embudo(funnel: list[tuple[str, int]], out: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 3.8))
    labels = [l for l, _ in funnel][::-1]
    values = [v for _, v in funnel][::-1]
    colors = ORDINAL[: len(values)]
    ax.barh(labels, values, color=colors, height=0.62, edgecolor=SURFACE, linewidth=2)
    for y, v in enumerate(values):
        ax.text(v, y, f"  {miles(v)}", va="center", fontsize=9, color=INK)
    ax.set_xlim(0, max(values) * 1.18)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: miles(x)))
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("titulares")
    _save(fig, out, "01_embudo_corpus.png", "Del export al corpus de entrenamiento",
          f"Cada barra aplica un filtro sobre la anterior. La muestra se toma de las noticias. {FUENTE}")


def volumen_mensual(monthly: pd.DataFrame, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(11, 4.4))
    wide = monthly.pivot(index="month", columns="source_id", values="titulares").sort_index()
    wide.index = pd.to_datetime(wide.index)
    # Agosto de 2026 sólo tiene 6 días de Petro: se omite para no dibujar una caída falsa.
    wide = wide[wide.index < pd.Timestamp("2026-08-01")]
    ax.axvspan(pd.Timestamp("2018-08-01"), pd.Timestamp("2020-12-31"), color=NEUTRAL, zorder=0)
    for m in MEDIA:
        ax.plot(wide.index, wide[m], color=MEDIA_COLORS[m], lw=1.6, label=MEDIA_NAMES[m])
    ax.set_ylim(0, wide.max().max() * 1.12)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: miles(x)))
    ax.set_ylabel("noticias por mes")
    _possession(ax)
    ax.text(pd.Timestamp("2018-09-01"), ax.get_ylim()[1] * 0.97, "RCN 2018–2020: sólo se conoce el mes",
            fontsize=8, color=INK2, va="top")
    _end_labels(ax, {m: wide[m] for m in MEDIA})
    ax.legend(ncol=5, loc="lower center", bbox_to_anchor=(0.5, 1.0))
    _save(fig, out, "02_volumen_mensual.png", "Noticias por mes y medio",
          "El volumen depende de lo que cada medio expone en sus sitemaps: por eso se comparan proporciones, "
          f"no conteos. Se omite agosto de 2026 (6 días). {FUENTE}")


def muestra_balanceada(cells: pd.DataFrame, per_cell: int, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 4.2))
    x = np.arange(len(MEDIA))
    width = 0.38
    for i, gov in enumerate(["duque", "petro"]):
        values = [int(cells.query("source_id == @m and government_id == @gov")["disponibles"].iloc[0]) for m in MEDIA]
        bars = ax.bar(x + (i - 0.5) * width, values, width, color=GOV_COLORS[gov], label=f"Gobierno {GOV_NAMES[gov]}",
                      edgecolor=SURFACE, linewidth=2)
        for b, v in zip(bars, values):
            ax.text(b.get_x() + b.get_width() / 2, v, miles(v), ha="center", va="bottom", fontsize=7.5, color=INK2)
    ax.axhline(per_cell, color=INK, lw=1.4)
    ax.set_xlim(-0.6, len(MEDIA) + 0.6)
    ax.text(len(MEDIA) - 0.45, per_cell, f"muestra:\n{miles(per_cell)}\npor celda", ha="left", va="center",
            fontsize=9, color=INK)
    ax.set_xticks(x, [MEDIA_NAMES[m] for m in MEDIA])
    ax.grid(axis="x", visible=False)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: miles(v)))
    ax.set_ylabel("noticias disponibles")
    ax.legend(loc="upper right")
    _save(fig, out, "03_muestra_balanceada.png", "La muestra iguala medios y gobiernos",
          f"El modelo se entrena con {miles(per_cell)} titulares por medio × gobierno ({miles(per_cell * 10)} en total) "
          f"y después se aplica a todas las noticias. {FUENTE}")


# ── preprocesamiento ─────────────────────────────────────────────────────────


def tokens_antes_despues(before: pd.Series, after: pd.Series, removed: set, bigrams: list, n: int, out: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 5.6))
    gray = AXIS
    bigram_color = "#0d366b"  # azul oscuro: variante de "se conserva", no un color de gobierno
    ax = axes[0]
    ax.barh(before.index[::-1], before.values[::-1] / n,
            color=[gray if w in removed else BLUE for w in before.index[::-1]], height=0.7)
    ax.set_title("Antes: sólo stopwords de NLTK")
    ax = axes[1]
    ax.barh([w.replace("_", " ") for w in after.index[::-1]], after.values[::-1] / n,
            color=[bigram_color if "_" in w else BLUE for w in after.index[::-1]], height=0.7)
    ax.set_title("Después: + stopwords de dominio y bigramas")
    for ax in axes:
        ax.xaxis.set_major_formatter(PercentFormatter(1, decimals=0))
        ax.set_xlabel("% de titulares que contienen la palabra")
        ax.grid(axis="y", visible=False)
    handles = [Patch(color=gray, label="se quita (stopword de dominio)"), Patch(color=BLUE, label="se conserva")]
    if any("_" in w for w in after.index):
        handles.append(Patch(color=bigram_color, label="bigrama unido por Phrases"))
    fig.legend(handles=handles, loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.04))
    ejemplos = ", ".join(b.replace("_", " ") for b in bigrams[:10])
    _save(fig, out, "04_tokens_antes_despues.png", "Las 20 palabras más frecuentes, antes y después de limpiar",
          f"Bigramas más frecuentes: {ejemplos}. Muestra aleatoria de {miles(n)} titulares. {FUENTE}", note_y=-0.07)


def ejemplo_titular(frame: pd.DataFrame, theta: np.ndarray, model, labels: dict, out: Path,
                    robust: dict | None = None) -> None:
    ntok = frame["tokens"].map(len).to_numpy()
    filled = np.nan_to_num(theta)
    conf = filled.max(axis=1)
    # Ilustración: un titular sobre la reforma pensional cuyo tópico mayor sea robusto.
    robustos = [k for k, v in (robust or {}).items() if v == "robusto"] or list(range(theta.shape[1]))
    top_is_robust = np.isin(filled.argmax(axis=1), robustos)
    cand = np.flatnonzero(frame["title"].str.contains("reforma pensional", case=False, na=False).to_numpy()
                          & (ntok >= 5) & (conf >= 0.5) & top_is_robust)
    if not len(cand):
        cand = np.flatnonzero((ntok >= 6) & (conf >= 0.5) & top_is_robust)
    i = int(cand[0])
    row = frame.iloc[i]
    bow = model.id2word.doc2bow(list(row["tokens"]))
    fig = plt.figure(figsize=(12, 5))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.35, 1], wspace=0.75)
    ax = fig.add_subplot(gs[0])
    ax.axis("off")
    steps = [
        ("1 · URL", row["url"]),
        ("2 · Titular reconstruido del slug", row["title"]),
        ("3 · Tokens (sin stopwords, bigramas unidos)", " · ".join(row["tokens"])),
        ("4 · Bolsa de palabras (id del diccionario: conteo)",
         "  ".join(f"{model.id2word[t]}={c}" for t, c in bow) or "(sin vocabulario)"),
    ]
    y = 0.97
    for head, body in steps:
        text = textwrap.fill(body, 54)
        lines = text.count("\n") + 1
        h = 0.07 + 0.045 * lines
        ax.add_patch(FancyBboxPatch((0.0, y - h), 1.0, h, boxstyle="round,pad=0.01,rounding_size=0.02",
                                    transform=ax.transAxes, facecolor=NEUTRAL, edgecolor=AXIS, lw=0.8))
        ax.text(0.02, y - 0.03, head, transform=ax.transAxes, fontsize=9, fontweight="bold", color=INK2, va="top")
        ax.text(0.02, y - 0.075, text, transform=ax.transAxes, fontsize=9, color=INK, va="top", family="DejaVu Sans Mono")
        y -= h + 0.05
        if y > 0.05:
            ax.annotate("", xy=(0.5, y + 0.012), xytext=(0.5, y + 0.045), xycoords="axes fraction",
                        arrowprops=dict(arrowstyle="-|>", color=MUTED, lw=1))
    ax2 = fig.add_subplot(gs[1])
    probs = theta[i]
    top = np.argsort(-probs)[:5][::-1]
    ax2.barh([textwrap.fill(etiqueta(labels, robust, int(t)), 24) for t in top], probs[top], color=BLUE, height=0.6)
    for yy, t in enumerate(top):
        ax2.text(probs[t], yy, f"  {probs[t]:.0%}", va="center", fontsize=9)
    ax2.set_xlim(0, 1)
    ax2.xaxis.set_major_formatter(PercentFormatter(1, decimals=0))
    ax2.grid(axis="y", visible=False)
    ax2.set_title("5 · Distribución de tópicos (θ), 5 mayores")
    _save(fig, out, "05_ejemplo_titular.png",
          f"Un titular paso a paso ({MEDIA_NAMES[row['source_id']]}, {row['published_date']:%Y-%m-%d})",
          "Ejemplo elegido para ilustrar (titular sobre la reforma pensional con tópico mayor robusto). El análisis usa "
          "la distribución completa θ de cada titular, no sólo el tópico mayor. " + FUENTE)


# ── entrenamiento ────────────────────────────────────────────────────────────


def seleccion_k(scores: pd.DataFrame, best: int, out: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for ax, col, title, fmt in [
        (axes[0], "coherence_cv", "Coherencia c_v (más alto es mejor)", "{:.3f}"),
        (axes[1], "heldout_perplexity", "Perplejidad en datos no vistos (más bajo es mejor)", "{:.0f}"),
    ]:
        ax.plot(scores["K"], scores[col], "o-", color=BLUE, ms=8, mec=SURFACE, mew=2)
        b = scores.loc[scores["K"] == best, col].iloc[0]
        ax.plot([best], [b], "o", color=RED, ms=10, mec=SURFACE, mew=2)
        ax.annotate(f"K = {best}: {fmt.format(b)}".replace(".", ","), (best, b), xytext=(10, -4),
                    textcoords="offset points", fontsize=9, color=INK, va="top")
        ax.set_title(title)
        ax.set_xlabel("número de tópicos K")
        ax.set_xticks(scores["K"])
    _save(fig, out, "06_seleccion_k.png", f"Elección del número de tópicos: K = {best}",
          "Se elige el K de mayor coherencia. La perplejidad en held-out (cota de gensim) crece con K en titulares "
          "cortos, así que no ayuda a elegir y no se usa sola. Una semilla por K. " + FUENTE)


def estabilidad(matrices: dict, jaccards: dict, out: Path) -> None:
    fig, axes = plt.subplots(1, len(matrices), figsize=(5.4 * len(matrices), 5), squeeze=False)
    for ax, (seed, mat) in zip(axes[0], matrices.items()):
        im = ax.imshow(mat, cmap=SEQ, vmin=0, vmax=1)
        jac = jaccards[seed]
        ax.set_title(f"Semilla 42 vs {seed}: Jaccard top-10 medio {jac.mean():.2f}".replace(".", ","))
        ax.set_xlabel(f"tópico emparejado (semilla {seed})")
        ax.set_ylabel("tópico (semilla 42)")
        ticks = np.arange(0, len(mat), 2)
        ax.set_xticks(ticks)
        ax.set_yticks(ticks)
        ax.grid(False)
    fig.colorbar(im, ax=axes[0].tolist(), shrink=0.8, label="similitud (1 − distancia JS)")
    _save(fig, out, "07_estabilidad_semillas.png", "¿Aparecen los mismos tópicos con otra semilla? Pocos",
          "Tópicos emparejados con el algoritmo húngaro; una diagonal oscura indicaría tópicos estables. Robustez de "
          "cada tópico = Jaccard medio de sus 10 palabras con su pareja: robusto ≥ 0,5; parcial ≥ 0,3; inestable < 0,3. "
          + FUENTE)


# ── tópicos ──────────────────────────────────────────────────────────────────


def topicos_palabras(model, labels: dict, prevalence: np.ndarray, out: Path, robust: dict | None = None) -> None:
    k = model.num_topics
    order = np.argsort(-prevalence)
    cols = 5
    rows = int(np.ceil(k / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(3.1 * cols, 2.5 * rows), squeeze=False)
    for ax, t in zip(axes.flat, order):
        words = model.show_topic(int(t), topn=10)[::-1]
        ax.barh([w.replace("_", " ") for w, _ in words], [p for _, p in words], color=BLUE, height=0.65)
        ax.set_title(textwrap.fill(f"{etiqueta(labels, robust, int(t))} · {prevalence[t]:.1%}", 30), fontsize=9)
        if robust and robust.get(int(t)) == "inestable":
            for bar in ax.patches:
                bar.set_color(AXIS)
        ax.tick_params(axis="y", labelsize=7.5)
        ax.tick_params(axis="x", labelsize=7)
        ax.xaxis.set_major_locator(MaxNLocator(3))
        ax.grid(axis="y", visible=False)
    for ax in list(axes.flat)[k:]:
        ax.axis("off")
    fig.tight_layout()
    _save(fig, out, "08_topicos_palabras.png", "Qué palabras van juntas: las 10 de mayor peso por tópico",
          "Ordenados por prevalencia (media de θ sobre todas las noticias). La etiqueta es una interpretación "
          f"humana, no la da el modelo. En gris, tópicos inestables entre semillas. {FUENTE}")


def mapa_topicos(topics: np.ndarray, labels: dict, prevalence: np.ndarray, out: Path, robust: dict | None = None) -> None:
    from scipy.spatial.distance import jensenshannon
    from sklearn.manifold import MDS

    k = len(topics)
    dist = np.array([[jensenshannon(a, b, base=2) for b in topics] for a in topics])
    xy = MDS(n_components=2, dissimilarity="precomputed", random_state=42, normalized_stress="auto").fit_transform(dist)
    fig, ax = plt.subplots(figsize=(10, 7.5))
    colors = [AXIS if (robust or {}).get(t) == "inestable" else BLUE for t in range(k)]
    ax.scatter(xy[:, 0], xy[:, 1], s=prevalence / prevalence.max() * 2200, color=colors, alpha=0.6,
               edgecolor=SURFACE, linewidth=2)
    for t in range(k):
        ax.text(xy[t, 0], xy[t, 1], textwrap.fill(labels.get(t, f"T{t}"), 18), ha="center", va="center",
                fontsize=7.5, color=INK)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    _save(fig, out, "09_mapa_topicos.png", "Mapa de tópicos: cercanía = vocabulario parecido",
          "Escalamiento multidimensional de la distancia Jensen-Shannon entre tópicos; el área es la prevalencia; en "
          "gris, tópicos inestables entre semillas. "
          f"Los ejes no tienen unidades. Versión interactiva: lda_visualization.html. {FUENTE}")


def confianza(conf: pd.DataFrame, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 4.2))
    bins = np.linspace(0, 1, 41)
    for m in MEDIA:
        v = conf.loc[conf["source_id"] == m, "topic_confidence"]
        h, e = np.histogram(v, bins=bins, density=True)
        ax.step(e[:-1], h, where="post", color=MEDIA_COLORS[m], lw=1.6, label=f"{MEDIA_NAMES[m]} (n={miles(len(v))})")
    ax.axvline(0.3, color=INK2, lw=1, ls="--")
    ax.text(0.3, ax.get_ylim()[1], " umbral 0,3", va="top", fontsize=8, color=INK2)
    ax.set_xlabel("probabilidad del tópico mayor de cada titular")
    ax.set_ylabel("densidad")
    ax.xaxis.set_major_formatter(PercentFormatter(1, decimals=0))
    ax.legend(loc="upper right")
    _save(fig, out, "10_confianza.png", "¿Qué tan claro es el tópico de cada titular?",
          "Con ~6 tokens por titular la probabilidad toma pocos valores posibles (de ahí los picos) y rara vez se "
          "concentra en un tópico. Por eso las comparaciones promedian la distribución completa en vez de contar el "
          f"tópico mayor. {FUENTE}")


# ── comparación ──────────────────────────────────────────────────────────────


def heatmap_medio_gobierno(cell: pd.DataFrame, labels: dict, out: Path, robust: dict | None = None) -> None:
    topics = list(cell.columns)
    order = cell.mean().sort_values(ascending=False).index
    cols = [(m, g) for m in MEDIA for g in ["duque", "petro"]]
    mat = np.array([[cell.loc[c, t] for c in cols] for t in order])
    fig, ax = plt.subplots(figsize=(11, 0.34 * len(order) + 2))
    im = ax.imshow(mat, cmap=SEQ, aspect="auto", vmin=0)
    vmax = mat.max()
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            ax.text(j, i, f"{mat[i, j]:.1%}".replace(".", ","), ha="center", va="center", fontsize=7,
                    color=SURFACE if mat[i, j] > vmax * 0.55 else INK)
    for j in range(2, len(cols), 2):
        ax.axvline(j - 0.5, color=SURFACE, lw=3)
    ax.set_xticks(range(len(cols)), [f"{SHORT[m]}\n{GOV_NAMES[g]}" for m, g in cols], fontsize=8)
    ax.set_yticks(range(len(order)), [etiqueta(labels, robust, int(t[1:])) for t in order], fontsize=8)
    ax.xaxis.tick_top()
    ax.grid(False)
    fig.colorbar(im, ax=ax, shrink=0.6, format=PercentFormatter(1, decimals=0), label="participación media")
    _save(fig, out, "11_heatmap_medio_gobierno.png", "Agenda de cada medio en cada gobierno",
          "Participación = media de θ de las noticias del medio en el gobierno; cada columna suma 100 %. "
          f"Tópicos ordenados por prevalencia. {FUENTE}")


def delta_relativo(deltas: pd.DataFrame, out: Path) -> None:
    deltas = deltas.assign(etiqueta=deltas["etiqueta"] + deltas["robustez"].map(SUFIJO))
    order = (deltas.groupby("etiqueta")["delta_rel_pp"].apply(lambda s: s.abs().max())
             .sort_values().index.tolist())
    fig, axes = plt.subplots(1, len(MEDIA), figsize=(16, 0.3 * len(order) + 2.2), sharey=True, sharex=True)
    for ax, m in zip(axes, MEDIA):
        d = deltas[deltas["source_id"] == m].set_index("etiqueta").loc[order]
        y = np.arange(len(order))
        color = np.where(d["delta_rel_pp"] >= 0, BLUE, RED)
        # Gris: tópico inestable o Δ que cambia de signo con otra semilla.
        dudoso = (d["robustez"].eq("inestable") | ~d["mismo_signo_otras_semillas"]).to_numpy()
        color = np.where(dudoso, AXIS, color)
        ax.hlines(y, d["delta_rel_low_pp"], d["delta_rel_high_pp"], color=color, lw=1.6)
        sig = d["delta_rel_p_holm"] < 0.05
        ax.scatter(d["delta_rel_pp"][sig], y[sig], color=color[sig], s=36, zorder=3, edgecolor=SURFACE, lw=1.5)
        ax.scatter(d["delta_rel_pp"][~sig], y[~sig], facecolor=SURFACE, edgecolor=color[~sig], s=36, zorder=3, lw=1.5)
        ax.axvline(0, color=INK2, lw=1)
        ax.set_title(MEDIA_NAMES[m])
        ax.grid(axis="y", visible=False)
        ax.set_xlabel("puntos porcentuales")
    axes[0].set_yticks(np.arange(len(order)), order, fontsize=8)
    fig.legend(handles=[
        Line2D([], [], marker="o", ls="", color=BLUE, label="más que los otros medios en Petro"),
        Line2D([], [], marker="o", ls="", color=RED, label="menos que los otros medios en Petro"),
        Line2D([], [], marker="o", ls="", markerfacecolor=SURFACE, markeredgecolor=INK2,
               label="no significativo (Holm ≥ 0,05)"),
        Line2D([], [], marker="o", ls="", color=AXIS, label="tópico inestable o cambia de signo con otra semilla"),
    ], loc="lower center", ncol=4, bbox_to_anchor=(0.5, -0.06))
    _save(fig, out, "12_delta_relativo.png",
          "Qué cambió en cada medio de Duque a Petro, más allá de la agenda general",
          "Δ relativo = (Petro − Duque) del medio menos el de los otros cuatro, sobre series mensuales; barras = "
          "IC 95 % por bootstrap de bloques de 3 meses; relleno = significativo tras Holm. " + FUENTE, note_y=-0.1)


def distancias_js(js: pd.DataFrame, out: Path) -> None:
    fig = plt.figure(figsize=(14, 4.6))
    gs = fig.add_gridspec(1, 3, width_ratios=[1, 1, 0.9], wspace=0.45)
    within = js[js["gobierno"].isin(["duque", "petro"])]
    vmax = within["js"].max()
    names = [SHORT[m] for m in MEDIA]
    for i, gov in enumerate(["duque", "petro"]):
        ax = fig.add_subplot(gs[i])
        mat = within[within["gobierno"] == gov].pivot(index="a", columns="b", values="js").loc[MEDIA, MEDIA].to_numpy()
        ax.imshow(mat, cmap=SEQ, vmin=0, vmax=vmax)
        for r in range(5):
            for c in range(5):
                ax.text(c, r, f"{mat[r, c]:.3f}", ha="center", va="center", fontsize=8,
                        color=SURFACE if mat[r, c] > vmax * 0.55 else INK)
        ax.set_xticks(range(5), names, rotation=35, ha="right", fontsize=8)
        ax.set_yticks(range(5), names if i == 0 else [""] * 5, fontsize=8)
        ax.set_title(f"Entre medios · {GOV_NAMES[gov]}")
        ax.grid(False)
    ax = fig.add_subplot(gs[2])
    self_ = js[js["gobierno"] == "duque→petro"].set_index("a").loc[MEDIA, "js"]
    ax.barh(names[::-1], self_.values[::-1], color=[MEDIA_COLORS[m] for m in MEDIA[::-1]], height=0.6)
    for y, v in enumerate(self_.values[::-1]):
        ax.text(v, y, f"  {v:.3f}", va="center", fontsize=8)
    ax.set_xlim(0, self_.max() * 1.3)
    ax.grid(axis="y", visible=False)
    ax.set_title("Cada medio consigo mismo: Duque → Petro")
    _save(fig, out, "13_distancias_js.png", "¿Qué tan distintas son las agendas?",
          "Distancia Jensen-Shannon (base 2, 0 = idénticas, 1 = sin tópicos en común) entre las participaciones de "
          f"tópicos. Misma escala en los dos mapas. {FUENTE}")


def series_topicos(monthly: pd.DataFrame, labels: dict, deltas: pd.DataFrame, out: Path,
                   robust: dict | None = None, n: int = 6) -> None:
    ranked = (deltas.assign(a=deltas["delta_pp"].abs()).groupby("topic")["a"].max()
              .sort_values(ascending=False).index.tolist())
    # Primero los tópicos robustos o parciales; los inestables sólo si faltan.
    pick = sorted(ranked, key=lambda k: (robust or {}).get(k) == "inestable")[:n]
    # Agosto de 2022 tiene filas de los dos gobiernos: se promedian en el mes.
    flat = monthly.groupby(level=["month", "source_id"]).mean()
    fig, axes = plt.subplots(2, 3, figsize=(15, 7.4), sharex=True)
    for ax, k in zip(axes.flat, pick):
        wide = flat[f"t{k}"].unstack("source_id")[MEDIA]
        wide.index = pd.to_datetime(wide.index)
        smooth = wide.rolling(3, min_periods=2).mean()
        ax.axvspan(pd.Timestamp("2018-08-01"), pd.Timestamp("2020-12-31"), color=NEUTRAL, zorder=0)
        for m in MEDIA:
            ax.plot(smooth.index, smooth[m], color=MEDIA_COLORS[m], lw=1.5, label=MEDIA_NAMES[m])
        ax.set_ylim(0, smooth.max().max() * 1.15)
        _possession(ax, label=False)
        ax.set_title(textwrap.fill(etiqueta(labels, robust, k), 40), fontsize=10)
        ax.yaxis.set_major_formatter(PercentFormatter(1, decimals=0))
        ax.xaxis.set_major_locator(mdates.YearLocator(2))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    handles, lbls = axes.flat[0].get_legend_handles_labels()
    handles.append(Line2D([], [], color=INK2, ls="--", lw=1))
    lbls.append("posesión de Petro (7-ago-2022)")
    fig.legend(handles, lbls, loc="lower center", ncol=6, bbox_to_anchor=(0.5, -0.04))
    fig.tight_layout()
    _save(fig, out, "14_series_topicos.png", f"Tópicos que más cambiaron entre gobiernos, mes a mes",
          "Participación mensual (media de θ), media móvil de 3 meses. Sombreado: RCN 2018–2020 sólo con fecha "
          f"mensual. {FUENTE}", note_y=-0.07)
