"""Calcula agregados del corpus y genera las figuras del informe.

Solo lee los datos; nunca imprime ni guarda texto de documentos.
Salidas:
  docs/figuras_datos.json         agregados (conteos, histogramas, proporciones)
  ../latex/figuras/*.png          cinco figuras a 300 dpi

Uso (desde proyecto/):
  .venv/bin/python scripts/figuras_informe.py              # todo
  .venv/bin/python scripts/figuras_informe.py --solo-gold  # solo la partición del gold
"""

from __future__ import annotations

import json
import math
import os
import sys
from collections import Counter
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DOCS = ROOT / "docs"
FIG_DIR = ROOT.parent / "latex" / "figuras"
ORIGINAL = Path.home() / ".open_corpus_co_es/data/dragons_rag/dragons_rag.parquet"
MODEL = "intfloat/multilingual-e5-small"
WINDOW, MODEL_LIMIT = 256, 512
BATCH = 4096

EXPECTED = {
    "docs_original": 169248,
    "docs_preparados": 146923,
    "chunks": 577324,
    "chunks_sobre_256": 40474,
    "max_tokens_retok": 258,
    "chunks_doc_mediana": 3,
    "chunks_doc_p95": 10,
    "chunks_doc_max": 426,
    "piloto": 500,
    "piloto_es": 220,
    "piloto_en": 280,
    "gold_dev": 20,
    "gold_test": 20,
}

DEV_IDS = (
    "G01 G02 G04 G09 G10 G12 G14 G16 G17 G18 "
    "G20 G21 G25 G27 G30 G31 G32 G33 G36 G39"
).split()
TEST_IDS = (
    "G03 G05 G06 G07 G08 G11 G13 G15 G19 G22 "
    "G23 G24 G26 G28 G29 G34 G35 G37 G38 G40"
).split()

SOURCE_LABEL = {"media_cloud": "Media Cloud", "bluesky": "Bluesky", "gdelt": "GDELT"}
SOURCE_ORDER = ["media_cloud", "bluesky", "gdelt"]
LANG_ORDER = ["es", "en"]

# Paleta única (slots de la paleta categórica de referencia, validada).
BLUE, ORANGE, AQUA, VIOLET = "#2a78d6", "#eb6834", "#1baf7a", "#6250d6"
BLUE_LIGHT = "#9ec5f4"
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#ffffff"
LANG_COLOR = {"es": BLUE, "en": ORANGE}

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 8,
        "axes.titlesize": 9,
        "axes.labelsize": 8,
        "axes.edgecolor": INK2,
        "axes.labelcolor": INK,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": GRID,
        "grid.linewidth": 0.6,
        "xtick.color": INK2,
        "ytick.color": INK2,
        "legend.frameon": False,
        "legend.fontsize": 7,
        "figure.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "savefig.dpi": 300,
    }
)
FIGSIZE = (3.5, 2.6)  # ancho de columna IEEE ≈ 3,5 in


def fmt(n: int) -> str:
    """Número con punto de miles (convención del informe)."""
    return f"{int(n):,}".replace(",", ".")


def check(name: str, got, errors: list[str]) -> None:
    want = EXPECTED[name]
    status = "OK" if got == want else "NO COINCIDE"
    print(f"  {name:22s} esperado={want!s:>8} calculado={got!s:>8}  {status}")
    if got != want:
        errors.append(f"{name}: esperado {want}, calculado {got}")


def int_hist(values) -> dict[str, int]:
    counts = Counter(int(v) for v in values)
    return {str(k): counts[k] for k in sorted(counts)}


def nested_counts(df: pd.DataFrame, a: str, b: str) -> dict:
    out: dict = {}
    for (x, y), n in df.groupby([a, b], dropna=False).size().items():
        x = "sin_valor" if pd.isna(x) else str(x)
        y = "sin_valor" if pd.isna(y) else str(y)
        out.setdefault(x, {})[y] = int(n)
    return out


# ---------------------------------------------------------------- cálculos
def corpus_counts() -> dict:
    prep = pq.read_table(DATA / "documentos_rag.parquet", columns=["source", "lang"]).to_pandas()
    result = {
        "preparado": {
            "total": len(prep),
            "por_fuente_idioma": nested_counts(prep, "source", "lang"),
            "por_idioma": {k: int(v) for k, v in prep["lang"].value_counts().items()},
        }
    }
    if ORIGINAL.exists():
        orig = pq.read_table(ORIGINAL, columns=["source", "language_base"]).to_pandas()
        lang = orig["language_base"].where(orig["language_base"].isin(LANG_ORDER), "otro")
        lang = lang.where(orig["language_base"].notna(), "sin_idioma")
        orig = orig.assign(idioma=lang)
        result["original"] = {
            "total": len(orig),
            "columna_idioma": "language_base (idioma declarado; 'lang' no existe antes de la preparación)",
            "por_fuente_idioma": nested_counts(orig, "source", "idioma"),
        }
    else:
        stats = json.loads((DOCS / "prepare_stats_es_en.json").read_text())
        result["original"] = {"total": stats["rows_input"], "fuente": "prepare_stats_es_en.json"}
    return result


def chunk_counts() -> tuple[dict, dict]:
    pf = pq.ParquetFile(DATA / "chunks_tok256.parquet")
    meta = pf.read(columns=["document_id", "token_count"]).to_pandas()
    per_doc = meta.groupby("document_id").size().to_numpy()
    chunks_doc = {
        "documentos": int(per_doc.size),
        "chunks": int(per_doc.sum()),
        "mediana": float(np.median(per_doc)),
        "p95": float(np.percentile(per_doc, 95)),
        "p99": float(np.percentile(per_doc, 99)),
        "maximo": int(per_doc.max()),
        "media": round(float(per_doc.mean()), 4),
        "histograma": int_hist(per_doc),
    }

    from transformers import AutoTokenizer

    tok = AutoTokenizer.from_pretrained(MODEL, local_files_only=True)
    retok = np.empty(pf.metadata.num_rows, dtype=np.int32)
    pos = 0
    for batch in pf.iter_batches(batch_size=BATCH, columns=["text"]):
        texts = batch.column("text").to_pylist()
        enc = tok(
            texts,
            add_special_tokens=False,
            truncation=False,
            return_attention_mask=False,
            return_token_type_ids=False,
        )
        retok[pos : pos + len(texts)] = [len(ids) for ids in enc["input_ids"]]
        pos += len(texts)
        del texts, enc
    assert pos == retok.size

    stored = meta["token_count"].to_numpy()
    tokens = {
        "chunks": int(retok.size),
        "token_count_guardado": {
            "maximo": int(stored.max()),
            "mediana": float(np.median(stored)),
            "histograma": int_hist(stored),
        },
        "retokenizado": {
            "maximo": int(retok.max()),
            "mediana": float(np.median(retok)),
            "sobre_256": int((retok > WINDOW).sum()),
            "sobre_512": int((retok > MODEL_LIMIT).sum()),
            "histograma": int_hist(retok),
        },
        "diferencia_retok_menos_guardado": int_hist(retok - stored),
        "tokenizador": MODEL,
        "add_special_tokens": False,
    }
    return chunks_doc, tokens


def pilot_vs_population(prep_counts: dict) -> dict:
    pil = pq.read_table(DATA / "piloto_documentos_500.parquet", columns=["source", "lang"]).to_pandas()
    pil_counts = nested_counts(pil, "source", "lang")
    pop_total = sum(sum(v.values()) for v in prep_counts.values())
    strata = []
    for s in SOURCE_ORDER:
        for l in LANG_ORDER:
            n_pop = prep_counts.get(s, {}).get(l, 0)
            n_pil = pil_counts.get(s, {}).get(l, 0)
            strata.append(
                {
                    "source": s,
                    "lang": l,
                    "poblacion_n": n_pop,
                    "poblacion_prop": round(n_pop / pop_total, 6),
                    "piloto_n": n_pil,
                    "piloto_prop": round(n_pil / len(pil), 6),
                }
            )
    return {
        "piloto_total": len(pil),
        "piloto_por_idioma": {k: int(v) for k, v in pil["lang"].value_counts().items()},
        "poblacion_total": pop_total,
        "estratos": strata,
    }


def gold_partition() -> dict:
    """Distribución observada del gold standard vigente (docs/gold_standard.csv).

    Estratos de respondibles por fuente esperada e idioma, más un estrato único de no
    respondibles (no tienen fuente). El orden coincide con la Tabla IV del informe.
    """
    g = pd.read_csv(DOCS / "gold_standard.csv", usecols=["id", "idioma", "tipo", "fuente_esperada", "split"],
                    keep_default_na=False)
    dev_ids = set(g.loc[g["split"] == "desarrollo", "id"])
    test_ids = set(g.loc[g["split"] == "prueba", "id"])
    assert dev_ids == set(DEV_IDS) and test_ids == set(TEST_IDS), "La partición no coincide con §4 del protocolo."

    def stratum(sub: pd.DataFrame, fuente: str, idioma: str) -> dict:
        return {
            "fuente_esperada": fuente,
            "idioma": idioma,
            "desarrollo": int((sub["split"] == "desarrollo").sum()),
            "prueba": int((sub["split"] == "prueba").sum()),
            "total": len(sub),
            "ids_desarrollo": sorted(sub.loc[sub["split"] == "desarrollo", "id"]),
            "ids_prueba": sorted(sub.loc[sub["split"] == "prueba", "id"]),
        }

    resp = g[g["tipo"] != "no_respondible"]
    strata = [stratum(sub, s, l) for (s, l), sub in resp.groupby(["fuente_esperada", "idioma"])]
    strata.append(stratum(g[g["tipo"] == "no_respondible"], "no_respondible", ""))
    return {
        "total": len(g),
        "desarrollo": int((g["split"] == "desarrollo").sum()),
        "prueba": int((g["split"] == "prueba").sum()),
        "respondibles": len(resp),
        "no_respondibles": int((g["tipo"] == "no_respondible").sum()),
        "fuente_ids": "docs/gold_standard.csv (columna split); listas de IDs en docs/protocolo_evaluacion.md §4",
        "estratos": strata,
    }


# ---------------------------------------------------------------- figuras
def save(fig, name: str) -> None:
    fig.tight_layout()
    fig.savefig(FIG_DIR / name)
    plt.close(fig)


def fig_corpus(data: dict) -> None:
    counts = data["corpus"]["preparado"]["por_fuente_idioma"]
    total = data["corpus"]["preparado"]["total"]
    x = np.arange(len(SOURCE_ORDER))
    w = 0.38
    fig, ax = plt.subplots(figsize=FIGSIZE)
    for i, l in enumerate(LANG_ORDER):
        vals = [counts.get(s, {}).get(l, 0) for s in SOURCE_ORDER]
        bars = ax.bar(x + (i - 0.5) * w, vals, w * 0.94, color=LANG_COLOR[l], label=l, edgecolor=SURFACE, linewidth=0.8)
        for b, v in zip(bars, vals):
            ax.annotate(fmt(v), (b.get_x() + b.get_width() / 2, v), xytext=(0, 2), textcoords="offset points",
                        ha="center", va="bottom", fontsize=6.5, color=INK)
    ax.set_xticks(x, [SOURCE_LABEL[s] for s in SOURCE_ORDER])
    ax.set_ylabel("Documentos (n)")
    ax.set_xlabel("Fuente")
    ax.set_title(f"Corpus preparado por fuente e idioma\n(n = {fmt(total)} documentos)")
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: fmt(v)))
    ax.set_ylim(0, ax.get_ylim()[1] * 1.08)
    ax.grid(axis="x", visible=False)
    ax.legend(title="Idioma", title_fontsize=7, loc="upper right")
    save(fig, "fig_corpus_estratos.png")


def fig_chunks(data: dict) -> None:
    cd = data["chunks_por_documento"]
    hist = {int(k): v for k, v in cd["histograma"].items()}
    xs = np.array(sorted(hist))
    ys = np.array([hist[k] for k in xs])
    fig, ax = plt.subplots(figsize=FIGSIZE)
    ax.bar(xs, ys, width=1.0, color=BLUE, linewidth=0)
    ax.set_yscale("log")
    ax.set_xscale("symlog", linthresh=10, linscale=1.0)
    ax.set_xlim(0.5, cd["maximo"] * 1.3)
    ax.set_xticks([1, 2, 3, 5, 10, 20, 50, 100, 200, 426])
    ax.get_xaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
    marks = [("mediana", cd["mediana"], INK, "--"), ("p95", cd["p95"], ORANGE, "-."), ("máximo", cd["maximo"], VIOLET, ":")]
    for label, v, c, ls in marks:
        ax.axvline(v, color=c, linestyle=ls, linewidth=1.1, label=f"{label} = {int(v)}")
    ax.set_xlabel("Chunks por documento (escala symlog)")
    ax.set_ylabel("Documentos (n, escala log)")
    ax.set_title(f"Chunks por documento\n({fmt(cd['documentos'])} documentos, {fmt(cd['chunks'])} chunks)")
    ax.legend(loc="upper right", bbox_to_anchor=(0.86, 1.0))
    save(fig, "fig_chunks_por_documento.png")


def fig_tokens(data: dict) -> None:
    rt = data["tokens_por_chunk"]["retokenizado"]
    hist = {int(k): v for k, v in rt["histograma"].items()}
    xs = np.array(sorted(hist))
    ys = np.array([hist[k] for k in xs])
    fig, ax = plt.subplots(figsize=FIGSIZE)
    ax.bar(xs, ys, width=1.0, color=BLUE, linewidth=0, label="chunks")
    over = xs > WINDOW
    ax.bar(xs[over], ys[over], width=1.0, color=ORANGE, linewidth=0, label=f"> {WINDOW} tokens")
    ax.set_yscale("log")
    ax.axvline(WINDOW, color=INK, linestyle="--", linewidth=1.0, label=f"{WINDOW}: ventana de diseño")
    ax.axvline(MODEL_LIMIT, color=VIOLET, linestyle=":", linewidth=1.2, label=f"{MODEL_LIMIT}: límite del modelo")
    ax.set_xlim(0, MODEL_LIMIT + 28)
    ax.set_ylim(1, max(ys) * 8)
    # Recuadro ampliado: la cola > 256 queda bajo la línea de 256 en la escala completa.
    ins = ax.inset_axes([0.58, 0.12, 0.32, 0.42])
    zx = np.arange(WINDOW - 2, rt["maximo"] + 1)
    zy = np.array([hist.get(int(k), 0) for k in zx])
    zc = [ORANGE if k > WINDOW else BLUE for k in zx]
    zb = ins.bar(zx, zy, 0.8, color=zc, linewidth=0)
    ins.set_yscale("log")
    ins.set_ylim(1, max(zy) * 2000)
    for b, v in zip(zb, zy):
        ins.annotate(fmt(v), (b.get_x() + b.get_width() / 2, v), xytext=(0, 1.5), textcoords="offset points",
                     ha="center", va="bottom", fontsize=4.8, color=INK, rotation=90)
    ins.set_xticks(zx, [str(k) for k in zx], fontsize=5)
    ins.tick_params(axis="y", labelsize=5)
    ins.set_title(f"Detalle 254–258\n{fmt(rt['sobre_256'])} chunks > {WINDOW}; máx. {rt['maximo']}", fontsize=5.5, color=INK)
    ins.grid(axis="x", visible=False)
    ins.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ins.spines[side].set_visible(True)
        ins.spines[side].set_color(INK2)
    ax.set_xlabel("Tokens por chunk al retokenizar (sin tokens especiales)")
    ax.set_ylabel("Chunks (n, escala log)")
    ax.set_title(f"Tokens por chunk retokenizado (n = {fmt(data['tokens_por_chunk']['chunks'])})")
    ax.legend(loc="upper left", fontsize=5.5, ncol=2)
    save(fig, "fig_tokens_retokenizacion.png")


def fig_pilot(data: dict) -> None:
    pv = data["piloto_vs_poblacion"]
    st = pv["estratos"]
    labels = [f"{SOURCE_LABEL[s['source']]} · {s['lang']}" for s in st]
    y = np.arange(len(st))[::-1]  # primer estrato arriba
    h = 0.38
    fig, ax = plt.subplots(figsize=(3.5, 2.9))
    series = [
        (f"Población (n = {fmt(pv['poblacion_total'])})", "poblacion_prop", "poblacion_n", BLUE_LIGHT),
        (f"Piloto (n = {pv['piloto_total']})", "piloto_prop", "piloto_n", BLUE),
    ]
    for i, (lab, key, nkey, c) in enumerate(series):
        vals = [100 * s[key] for s in st]
        bars = ax.barh(y + (0.5 - i) * h, vals, h * 0.94, color=c, label=lab, edgecolor=SURFACE, linewidth=0.8)
        for b, v, s in zip(bars, vals, st):
            ax.annotate(f"{v:.1f} % ({fmt(s[nkey])})", (v, b.get_y() + b.get_height() / 2), xytext=(2, 0),
                        textcoords="offset points", ha="left", va="center", fontsize=5.5, color=INK)
    ax.set_yticks(y, labels, fontsize=7)
    ax.set_xlabel("Proporción del total (%)")
    ax.set_ylabel("Estrato (fuente · idioma)")
    ax.set_title("Piloto frente a población por estrato")
    ax.set_xlim(0, 58)
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower right")
    save(fig, "fig_piloto_vs_poblacion.png")


def fig_gold(data: dict) -> None:
    gp = data["particion_gold"]
    st = gp["estratos"]
    labels = [
        "No\nresp." if s["fuente_esperada"] == "no_respondible"
        else f"{SOURCE_LABEL[s['fuente_esperada']].replace(' ', chr(10))}\n{s['idioma']}"
        for s in st
    ]
    x = np.arange(len(st))
    dev = np.array([s["desarrollo"] for s in st])
    test = np.array([s["prueba"] for s in st])
    fig, ax = plt.subplots(figsize=FIGSIZE)
    ax.bar(x, dev, 0.6, color=AQUA, label=f"Desarrollo (n = {gp['desarrollo']})", edgecolor=SURFACE, linewidth=1.2)
    ax.bar(x, test, 0.6, bottom=dev, color=VIOLET, label=f"Prueba (n = {gp['prueba']})", edgecolor=SURFACE, linewidth=1.2)
    for xi, d, t in zip(x, dev, test):
        if d:
            ax.text(xi, d / 2, str(d), ha="center", va="center", fontsize=6.5, color=INK)
        if t:
            ax.text(xi, d + t / 2, str(t), ha="center", va="center", fontsize=6.5, color=SURFACE)
        ax.text(xi, d + t + 0.3, f"total {d + t}", ha="center", va="bottom", fontsize=6, color=INK2)
    ax.set_xticks(x, labels, fontsize=6.5)
    ax.set_ylabel("Preguntas (n)")
    ax.set_xlabel("Estrato (fuente esperada × idioma)")
    ax.set_title(f"Gold standard observado ({gp['desarrollo']}/{gp['prueba']}, n = {gp['total']})")
    ax.set_ylim(0, max(dev + test) * 1.25)
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper left")
    save(fig, "fig_particion_gold.png")


def main_solo_gold() -> int:
    """Actualiza solo la partición del gold: la sección particion_gold de figuras_datos.json
    y fig_particion_gold.png. No recalcula el corpus ni toca las otras figuras."""
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    path = DOCS / "figuras_datos.json"
    data = json.loads(path.read_text())
    data["particion_gold"] = gold_partition()
    errors: list[str] = []
    check("gold_dev", data["particion_gold"]["desarrollo"], errors)
    check("gold_test", data["particion_gold"]["prueba"], errors)
    if errors:
        print("ERROR: la partición no coincide; no se genera la figura.")
        return 1
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    fig_gold(data)
    print("Figura en", FIG_DIR / "fig_particion_gold.png")
    return 0


def main() -> int:
    if "--solo-gold" in sys.argv[1:]:
        return main_solo_gold()
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    print("Calculando agregados...")
    corpus = corpus_counts()
    chunks_doc, tokens = chunk_counts()
    data = {
        "nota": "Solo agregados; no contiene texto de documentos.",
        "corpus": corpus,
        "chunks_por_documento": chunks_doc,
        "tokens_por_chunk": tokens,
        "piloto_vs_poblacion": pilot_vs_population(corpus["preparado"]["por_fuente_idioma"]),
        "particion_gold": gold_partition(),
    }
    (DOCS / "figuras_datos.json").write_text(json.dumps(data, ensure_ascii=False, indent=2))

    print("Validación contra cifras del informe:")
    errors: list[str] = []
    pv = data["piloto_vs_poblacion"]
    check("docs_original", corpus["original"]["total"], errors)
    check("docs_preparados", corpus["preparado"]["total"], errors)
    check("chunks", chunks_doc["chunks"], errors)
    check("chunks_sobre_256", tokens["retokenizado"]["sobre_256"], errors)
    check("max_tokens_retok", tokens["retokenizado"]["maximo"], errors)
    check("chunks_doc_mediana", int(chunks_doc["mediana"]) if chunks_doc["mediana"].is_integer() else chunks_doc["mediana"], errors)
    check("chunks_doc_p95", int(chunks_doc["p95"]) if float(chunks_doc["p95"]).is_integer() else chunks_doc["p95"], errors)
    check("chunks_doc_max", chunks_doc["maximo"], errors)
    check("piloto", pv["piloto_total"], errors)
    check("piloto_es", pv["piloto_por_idioma"].get("es"), errors)
    check("piloto_en", pv["piloto_por_idioma"].get("en"), errors)
    check("gold_dev", data["particion_gold"]["desarrollo"], errors)
    check("gold_test", data["particion_gold"]["prueba"], errors)
    if errors:
        print("ERROR: hay totales que no coinciden; no se generan figuras.")
        for e in errors:
            print("  -", e)
        return 1

    fig_corpus(data)
    fig_chunks(data)
    fig_tokens(data)
    fig_pilot(data)
    fig_gold(data)
    print("Figuras en", FIG_DIR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
